from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.settings import SettingsDep
from adapters.settings import StorageSettings
from adapters.storage import (
    ImageStore,
    LoraPreviewStore,
    MinioImageStore,
    PresetPreviewStore,
)


@lru_cache(maxsize=4)
def _store(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    secure: bool,
    retention_hours: int,
) -> MinioImageStore:
    """One client per process: the HTTP pool is reused between requests."""
    return MinioImageStore(
        StorageSettings(
            MINIO_ENDPOINT=endpoint,
            MINIO_ACCESS_KEY=access_key,
            MINIO_SECRET_KEY=secret_key,
            MINIO_BUCKET=bucket,
            MINIO_SECURE=secure,
            MINIO_RETENTION_HOURS=retention_hours,
        )
    )


async def get_image_store(settings: SettingsDep) -> AsyncIterator[ImageStore | None]:
    config = settings.STORAGE_SETTINGS
    if not config.enabled:
        yield None
        return
    yield _store(
        config.MINIO_ENDPOINT,
        config.MINIO_ACCESS_KEY,
        config.MINIO_SECRET_KEY,
        config.MINIO_BUCKET,
        config.MINIO_SECURE,
        config.MINIO_RETENTION_HOURS,
    )


ImageStoreDep = Annotated[ImageStore | None, Depends(get_image_store)]


async def get_preset_preview_store(
    settings: SettingsDep,
) -> AsyncIterator[PresetPreviewStore | None]:
    config = settings.STORAGE_SETTINGS
    if not config.enabled:
        yield None
        return
    yield _store(
        config.MINIO_ENDPOINT,
        config.MINIO_ACCESS_KEY,
        config.MINIO_SECRET_KEY,
        config.MINIO_BUCKET,
        config.MINIO_SECURE,
        config.MINIO_RETENTION_HOURS,
    )


PresetPreviewStoreDep = Annotated[
    PresetPreviewStore | None, Depends(get_preset_preview_store)
]


async def get_lora_preview_store(
    settings: SettingsDep,
) -> AsyncIterator[LoraPreviewStore | None]:
    config = settings.STORAGE_SETTINGS
    if not config.enabled:
        yield None
        return
    yield _store(
        config.MINIO_ENDPOINT,
        config.MINIO_ACCESS_KEY,
        config.MINIO_SECRET_KEY,
        config.MINIO_BUCKET,
        config.MINIO_SECURE,
        config.MINIO_RETENTION_HOURS,
    )


LoraPreviewStoreDep = Annotated[
    LoraPreviewStore | None, Depends(get_lora_preview_store)
]
