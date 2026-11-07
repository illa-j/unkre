from pydantic import Field, field_validator

from adapters.settings.base import BaseAppSettings


class StorageSettings(BaseAppSettings):
    """Temporary MinIO cache for generated images.

    The database keeps only the generation record; finished images are parked
    in MinIO so any browser can fetch them, then disappear after the retention
    window (24 hours by default) unless the user already saved a local copy.
    """

    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "unkre-images"
    MINIO_SECURE: bool = False
    MINIO_RETENTION_HOURS: int = Field(default=24, ge=1, le=720)

    @field_validator("MINIO_ENDPOINT", mode="before")
    @classmethod
    def strip_scheme(cls, value: object) -> str:
        raw = str(value or "").strip()
        for prefix in ("https://", "http://"):
            if raw.startswith(prefix):
                return raw.removeprefix(prefix).rstrip("/")
        return raw.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(
            self.MINIO_ENDPOINT
            and self.MINIO_ACCESS_KEY.strip()
            and self.MINIO_SECRET_KEY.strip()
        )
