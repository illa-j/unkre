import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from itertools import islice
from logging import getLogger
from math import ceil
from typing import Protocol
from uuid import UUID

import urllib3
from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.error import S3Error
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

from adapters.settings import StorageSettings
from adapters.storage.images import (
    StoredGenerationImage,
    generation_image_key,
    image_media_type,
    lora_preview_key,
    preset_preview_key,
)

logger = getLogger(__name__)
LIFECYCLE_RULE_ID = "expire-generation-images"


class ImageStore(Protocol):
    async def put(self, generation_id: UUID | str, data: bytes) -> bool: ...

    async def get(self, generation_id: UUID | str) -> tuple[bytes, str] | None: ...

    async def delete(self, generation_id: UUID | str) -> bool: ...

    async def list_generation_images(
        self, *, after: str | None = None, limit: int = 100
    ) -> list[StoredGenerationImage]: ...

    async def close(self) -> None: ...


class PresetPreviewStore(Protocol):
    async def put_preset_preview(self, preview_id: UUID | str, data: bytes) -> bool: ...

    async def get_preset_preview(
        self, preview_id: UUID | str
    ) -> tuple[bytes, str] | None: ...

    async def delete_preset_preview(self, preview_id: UUID | str) -> None: ...


class LoraPreviewStore(Protocol):
    async def put_lora_preview(self, preview_id: UUID | str, data: bytes) -> bool: ...

    async def get_lora_preview(
        self, preview_id: UUID | str
    ) -> tuple[bytes, str] | None: ...

    async def delete_lora_preview(self, preview_id: UUID | str) -> None: ...


class MinioImageStore:
    """Temporary image cache in MinIO with an application-level expiry check.

    Generated images live under ``generations/`` and are covered by the bucket
    lifecycle rule. Preset and LoRA previews use separate prefixes and persist
    until their catalog records are removed.
    """

    def __init__(
        self,
        settings: StorageSettings,
        client: Minio | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            http_client=urllib3.PoolManager(
                timeout=urllib3.util.Timeout(connect=3.0, read=15.0),
                retries=urllib3.Retry(total=1, backoff_factor=0.2),
            ),
        )
        self._bucket = settings.MINIO_BUCKET
        self._retention = timedelta(hours=settings.MINIO_RETENTION_HOURS)
        self._ready = False
        self._lock = asyncio.Lock()

    async def put(self, generation_id: UUID | str, data: bytes) -> bool:
        media = image_media_type(data)
        if media is None:
            logger.warning(
                "Skipped caching generation %s: unsupported image", generation_id
            )
            return False
        await self._ensure_bucket()
        media_type, _ = media
        try:
            await asyncio.to_thread(
                self._put, generation_image_key(generation_id), data, media_type
            )
            return True
        except (S3Error, urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO upload for %s failed (%s)",
                generation_id,
                type(exc).__name__,
            )
            return False

    async def get(self, generation_id: UUID | str) -> tuple[bytes, str] | None:
        await self._ensure_bucket()
        key = generation_image_key(generation_id)
        try:
            stat = await asyncio.to_thread(self._client.stat_object, self._bucket, key)
        except S3Error as exc:
            if exc.code not in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                logger.warning("MinIO stat for %s failed (%s)", generation_id, exc.code)
            return None
        except (urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO stat for %s failed (%s)",
                generation_id,
                type(exc).__name__,
            )
            return None
        if self._expired(stat.last_modified):
            await self.delete(generation_id)
            return None
        try:
            data, media_type = await asyncio.to_thread(self._read, key)
        except S3Error as exc:
            if exc.code not in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                logger.warning("MinIO read for %s failed (%s)", generation_id, exc.code)
            return None
        except (urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO read for %s failed (%s)",
                generation_id,
                type(exc).__name__,
            )
            return None
        detected = image_media_type(data)
        if detected is None:
            logger.warning("Cached generation %s is not an image", generation_id)
            return None
        detected_type, _ = detected
        return data, media_type if media_type.startswith("image/") else detected_type

    async def delete(self, generation_id: UUID | str) -> bool:
        await self._ensure_bucket()
        try:
            await asyncio.to_thread(
                self._client.remove_object,
                self._bucket,
                generation_image_key(generation_id),
            )
            return True
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                return True
            logger.warning("MinIO delete for %s failed (%s)", generation_id, exc.code)
            return False
        except (urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO delete for %s failed (%s)",
                generation_id,
                type(exc).__name__,
            )
            return False

    async def list_generation_images(
        self, *, after: str | None = None, limit: int = 100
    ) -> list[StoredGenerationImage]:
        await self._ensure_bucket()

        def read_page() -> list[StoredGenerationImage]:
            try:
                objects = self._client.list_objects(
                    self._bucket,
                    prefix="generations/",
                    recursive=True,
                    start_after=after,
                )
                return [
                    StoredGenerationImage(item.object_name, item.last_modified)
                    for item in islice(objects, limit)
                ]
            except S3Error as exc:
                if exc.code == "NoSuchBucket":
                    return []
                raise

        return await asyncio.to_thread(read_page)

    async def put_preset_preview(self, preview_id: UUID | str, data: bytes) -> bool:
        return await self._put_preview(preset_preview_key(preview_id), data, "preset")

    async def get_preset_preview(
        self, preview_id: UUID | str
    ) -> tuple[bytes, str] | None:
        return await self._get_preview(preset_preview_key(preview_id), "preset")

    async def delete_preset_preview(self, preview_id: UUID | str) -> None:
        await self._delete_preview(preset_preview_key(preview_id), "preset")

    async def put_lora_preview(self, preview_id: UUID | str, data: bytes) -> bool:
        return await self._put_preview(lora_preview_key(preview_id), data, "LoRA")

    async def get_lora_preview(
        self, preview_id: UUID | str
    ) -> tuple[bytes, str] | None:
        return await self._get_preview(lora_preview_key(preview_id), "LoRA")

    async def delete_lora_preview(self, preview_id: UUID | str) -> None:
        await self._delete_preview(lora_preview_key(preview_id), "LoRA")

    async def _put_preview(self, key: str, data: bytes, label: str) -> bool:
        media = image_media_type(data)
        if media is None:
            return False
        await self._ensure_bucket()
        media_type, _ = media
        try:
            await asyncio.to_thread(self._put, key, data, media_type)
            return True
        except (S3Error, urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO %s preview upload for %s failed (%s)",
                label,
                key.rsplit("/", 1)[-1],
                type(exc).__name__,
            )
            return False

    async def _get_preview(self, key: str, label: str) -> tuple[bytes, str] | None:
        await self._ensure_bucket()
        try:
            data, media_type = await asyncio.to_thread(self._read, key)
        except S3Error as exc:
            if exc.code not in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                logger.warning(
                    "MinIO %s preview read for %s failed (%s)",
                    label,
                    key.rsplit("/", 1)[-1],
                    exc.code,
                )
            return None
        except (urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO %s preview read for %s failed (%s)",
                label,
                key.rsplit("/", 1)[-1],
                type(exc).__name__,
            )
            return None
        detected = image_media_type(data)
        if detected is None:
            return None
        detected_type, _ = detected
        return data, media_type if media_type.startswith("image/") else detected_type

    async def _delete_preview(self, key: str, label: str) -> None:
        await self._ensure_bucket()
        try:
            await asyncio.to_thread(self._client.remove_object, self._bucket, key)
        except (S3Error, urllib3.exceptions.HTTPError, OSError) as exc:
            logger.warning(
                "MinIO %s preview delete for %s failed (%s)",
                label,
                key.rsplit("/", 1)[-1],
                type(exc).__name__,
            )

    async def close(self) -> None:
        return None

    def _expired(self, last_modified: datetime | None) -> bool:
        if last_modified is None:
            return False
        if last_modified.tzinfo is None:
            last_modified = last_modified.replace(tzinfo=UTC)
        return datetime.now(UTC) - last_modified > self._retention

    def _put(self, key: str, data: bytes, media_type: str) -> None:
        self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=media_type,
        )

    def _read(self, key: str) -> tuple[bytes, str]:
        response = self._client.get_object(self._bucket, key)
        try:
            data = response.read()
            media_type = (
                (response.headers.get("Content-Type") or "").split(";")[0].strip()
            )
        finally:
            response.close()
            response.release_conn()
        return data, media_type

    async def _ensure_bucket(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            try:
                self._ready = await asyncio.to_thread(self._prepare_bucket)
            except (S3Error, urllib3.exceptions.HTTPError, OSError) as exc:
                logger.warning(
                    "MinIO bucket %s is unavailable (%s)",
                    self._bucket,
                    type(exc).__name__,
                )

    def _prepare_bucket(self) -> bool:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        try:
            existing = self._client.get_bucket_lifecycle(self._bucket)
            rules = [
                rule
                for rule in (existing.rules if existing is not None else [])
                if rule.rule_id != LIFECYCLE_RULE_ID
            ]
            self._client.set_bucket_lifecycle(
                self._bucket,
                LifecycleConfig(
                    [
                        *rules,
                        Rule(
                            ENABLED,
                            rule_filter=Filter(prefix="generations/"),
                            rule_id=LIFECYCLE_RULE_ID,
                            expiration=Expiration(
                                days=ceil(self._settings.MINIO_RETENTION_HOURS / 24)
                            ),
                        ),
                    ]
                ),
            )
            return True
        except S3Error as exc:
            logger.warning("MinIO lifecycle rule was not applied (%s)", exc.code)
            return False
