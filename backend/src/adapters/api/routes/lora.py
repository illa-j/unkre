from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from adapters.api.dependencies.images import LoraPreviewStoreDep

router = APIRouter(prefix="/loras", tags=["loras"])


@router.get("/previews/{preview_id}", response_class=Response)
async def get_lora_preview(
    preview_id: UUID, store: LoraPreviewStoreDep
) -> Response:
    preview = await store.get_lora_preview(preview_id) if store else None
    if preview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preview not found")
    data, media_type = preview
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Disposition": f'inline; filename="{preview_id}"',
        },
    )
