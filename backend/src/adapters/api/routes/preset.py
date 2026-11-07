from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status

from adapters.api.dependencies.images import PresetPreviewStoreDep
from adapters.api.dependencies.preset import PresetServiceDep
from adapters.api.dependencies.user import CurrentUserDep
from adapters.api.preset_previews import store_uploaded_preview
from adapters.api.schemas.preset import (
    CreatePresetRequest,
    PresetFavoriteResponse,
    PresetLikeResponse,
    PresetPreviewResponse,
    PresetResponse,
    PresetSaveResponse,
    UpdatePresetRequest,
)
from domain.entities.preset import GenerationPreset

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("", response_model=list[PresetResponse])
async def get_presets(
    user: CurrentUserDep,
    service: PresetServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[GenerationPreset]:
    return await service.get_all(user.id, limit=limit, offset=offset)


@router.post(
    "/previews",
    response_model=PresetPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_preset_preview(
    user: CurrentUserDep,
    store: PresetPreviewStoreDep,
    file: UploadFile = File(...),
) -> PresetPreviewResponse:
    return await store_uploaded_preview(file, store)


@router.get("/previews/{preview_id}", response_class=Response)
async def get_preset_preview(
    preview_id: UUID, store: PresetPreviewStoreDep
) -> Response:
    preview = await store.get_preset_preview(preview_id) if store else None
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


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> GenerationPreset:
    return await service.get_accessible(user.id, preset_id)


@router.post("", response_model=PresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    data: CreatePresetRequest, user: CurrentUserDep, service: PresetServiceDep
) -> GenerationPreset:
    return await service.create(
        user.id,
        name=data.name,
        workflow_id=data.workflow_id,
        prompt=data.prompt,
        negative_prompt=data.negative_prompt,
        description=data.description,
        loras_strength=data.loras_strength,
        seed=data.seed,
        is_public=data.is_public,
        preview_urls=data.preview_urls,
    )


@router.patch("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: UUID,
    data: UpdatePresetRequest,
    user: CurrentUserDep,
    service: PresetServiceDep,
) -> GenerationPreset:
    return await service.update(
        user.id, preset_id, data.model_dump(exclude_unset=True)
    )


@router.put("/{preset_id}/favorite", response_model=PresetFavoriteResponse)
async def favorite_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> PresetFavoriteResponse:
    count, favorite = await service.favorite(user.id, preset_id)
    return PresetFavoriteResponse(
        favorites_count=count, is_favorite=favorite
    )


@router.put("/{preset_id}/like", response_model=PresetLikeResponse)
async def like_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> PresetLikeResponse:
    count, liked = await service.favorite(user.id, preset_id)
    return PresetLikeResponse(likes_count=count, is_liked=liked)


@router.delete("/{preset_id}/like", response_model=PresetLikeResponse)
async def unlike_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> PresetLikeResponse:
    count, liked = await service.unfavorite(user.id, preset_id)
    return PresetLikeResponse(likes_count=count, is_liked=liked)


@router.put("/{preset_id}/save", response_model=PresetSaveResponse)
async def save_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> PresetSaveResponse:
    return PresetSaveResponse(is_saved=await service.save(user.id, preset_id))


@router.delete("/{preset_id}/save", response_model=PresetSaveResponse)
async def unsave_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> PresetSaveResponse:
    return PresetSaveResponse(is_saved=await service.unsave(user.id, preset_id))


@router.delete("/{preset_id}/favorite", response_model=PresetFavoriteResponse)
async def unfavorite_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> PresetFavoriteResponse:
    count, favorite = await service.unfavorite(user.id, preset_id)
    return PresetFavoriteResponse(
        favorites_count=count, is_favorite=favorite
    )


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: UUID, user: CurrentUserDep, service: PresetServiceDep
) -> Response:
    await service.delete(user.id, preset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
