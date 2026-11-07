"""Image signatures shared by the API and the storage adapter."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"


@dataclass(frozen=True)
class StoredGenerationImage:
    key: str
    last_modified: datetime | None


def image_media_type(data: bytes) -> tuple[str, str] | None:
    """Return ``(media_type, extension)`` for a supported image, else ``None``."""
    if data.startswith(PNG_SIGNATURE):
        return "image/png", "png"
    if data.startswith(JPEG_SIGNATURE):
        return "image/jpeg", "jpg"
    if data.startswith(WEBP_RIFF) and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def generation_image_key(generation_id: UUID | str) -> str:
    """One object per generation; the extension is carried by Content-Type."""
    return f"generations/{generation_id}"


def preset_preview_key(preview_id: UUID | str) -> str:
    """Persistent preset preview; never covered by the generation lifecycle."""
    return f"preset-previews/{preview_id}"


def lora_preview_key(preview_id: UUID | str) -> str:
    """Persistent LoRA preview; never covered by the generation lifecycle."""
    return f"lora-previews/{preview_id}"
