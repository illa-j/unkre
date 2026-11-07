from uuid import uuid7

from fastapi import HTTPException, UploadFile, status

from adapters.api.schemas.preset import PresetPreviewResponse
from adapters.storage import LoraPreviewStore, image_media_type

MAX_PREVIEW_BYTES = 10 * 1024 * 1024
PREVIEW_PATH_PREFIX = "/api/loras/previews/"


async def store_uploaded_lora_preview(
    file: UploadFile, store: LoraPreviewStore | None
) -> PresetPreviewResponse:
    if store is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Preview storage is not configured",
        )
    data = await file.read(MAX_PREVIEW_BYTES + 1)
    if len(data) > MAX_PREVIEW_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "Preview images must be 10 MB or smaller",
        )
    if image_media_type(data) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Choose a PNG, JPEG or WebP image",
        )
    preview_id = uuid7()
    if not await store.put_lora_preview(preview_id, data):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Preview storage is unavailable",
        )
    return PresetPreviewResponse(
        id=preview_id,
        url=f"{PREVIEW_PATH_PREFIX}{preview_id}",
    )
