from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status

from adapters.api.dependencies.admin import CurrentAdminDep
from adapters.api.dependencies.images import PresetPreviewStoreDep
from adapters.api.dependencies.preset import PresetServiceDep
from adapters.api.preset_previews import store_uploaded_preview
from adapters.api.schemas.admin_preset import (
    AdminCreatePresetRequest,
    AdminPresetPage,
)
from adapters.api.schemas.preset import (
    PresetPreviewResponse,
    PresetResponse,
    UpdatePresetRequest,
)
from domain.entities.preset import GenerationPreset
from domain.exceptions.preset import PresetNotFoundError

router = APIRouter(prefix="/admins", tags=["admins"])


@router.post(
    "/presets/previews",
    response_model=PresetPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_admin_preset_preview(
    admin: CurrentAdminDep,
    store: PresetPreviewStoreDep,
    file: UploadFile = File(...),
) -> PresetPreviewResponse:
    return await store_uploaded_preview(file, store)


@router.get("/presets", response_model=AdminPresetPage)
async def get_presets(
    admin: CurrentAdminDep,
    service: PresetServiceDep,
    query: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminPresetPage:
    items, total = await service.get_admin(
        query=query, limit=limit, offset=offset
    )
    return AdminPresetPage(
        total=total,
        items=[PresetResponse.model_validate(item) for item in items],
    )


@router.post(
    "/presets", response_model=PresetResponse, status_code=status.HTTP_201_CREATED
)
async def create_preset(
    data: AdminCreatePresetRequest,
    admin: CurrentAdminDep,
    service: PresetServiceDep,
) -> GenerationPreset:
    return await service.create_admin(
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


@router.patch("/presets/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: UUID,
    data: UpdatePresetRequest,
    admin: CurrentAdminDep,
    service: PresetServiceDep,
) -> GenerationPreset:
    try:
        return await service.update_admin(
            preset_id, data.model_dump(exclude_unset=True)
        )
    except PresetNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preset not found") from exc


@router.delete("/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: UUID,
    admin: CurrentAdminDep,
    service: PresetServiceDep,
) -> Response:
    try:
        await service.delete_admin(preset_id)
    except PresetNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preset not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
