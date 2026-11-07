from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status

from adapters.api.dependencies.admin import CurrentAdminDep
from adapters.api.dependencies.admin_catalog import AdminCatalogServiceDep
from adapters.api.dependencies.images import LoraPreviewStoreDep
from adapters.api.lora_previews import store_uploaded_lora_preview
from adapters.api.schemas.admin_catalog import (
    AdminLoraItem,
    AdminLoraPage,
    CreateLoraRequest,
    CreateWorkflowRequest,
    SetWorkflowLorasRequest,
    UpdateLoraRequest,
    UpdateWorkflowRequest,
)
from adapters.api.schemas.preset import PresetPreviewResponse
from adapters.api.schemas.workflow import WorkflowResponse
from domain.exceptions.catalog import CatalogConflictError

router = APIRouter(prefix="/admins", tags=["admins"])


def _conflict(exc: CatalogConflictError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
    )


@router.post(
    "/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED
)
async def create_workflow(
    data: CreateWorkflowRequest,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> WorkflowResponse:
    try:
        row = await service.create_workflow(
            name=data.name,
            description=data.description,
            generation_credits=data.generation_credits,
            is_active=data.is_active,
        )
    except CatalogConflictError as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
    response = await service.workflow_response(row.id)
    if response is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Workflow was not stored")
    return response


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    data: UpdateWorkflowRequest,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> WorkflowResponse:
    try:
        row = await service.update_workflow(
            workflow_id, data.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise _invalid(exc) from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    response = await service.workflow_response(workflow_id)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return response


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> Response:
    try:
        deleted = await service.delete_workflow(workflow_id)
    except CatalogConflictError as exc:
        raise _conflict(exc) from exc
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/workflows/{workflow_id}/loras", response_model=WorkflowResponse)
async def set_workflow_loras(
    workflow_id: UUID,
    data: SetWorkflowLorasRequest,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> WorkflowResponse:
    try:
        updated = await service.set_workflow_loras(
            workflow_id,
            [(item.lora_id, item.recommended_strength) for item in data.items],
        )
    except ValueError as exc:
        raise _invalid(exc) from exc
    if not updated:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Workflow or LoRA not found"
        )
    response = await service.workflow_response(workflow_id)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return response


@router.post(
    "/loras/previews",
    response_model=PresetPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_lora_preview(
    admin: CurrentAdminDep,
    store: LoraPreviewStoreDep,
    file: UploadFile = File(...),
) -> PresetPreviewResponse:
    return await store_uploaded_lora_preview(file, store)


@router.get("/loras", response_model=AdminLoraPage)
async def get_loras(
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
    query: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminLoraPage:
    rows, total = await service.loras(query=query, limit=limit, offset=offset)
    return AdminLoraPage(
        total=total,
        items=[
            AdminLoraItem(
                id=row.id,
                name=row.name,
                description=row.description,
                preview_urls=list(row.preview_urls or []),
                is_nsfw=bool(row.is_nsfw),
                workflow_count=count,
            )
            for row, count in rows
        ],
    )


@router.post("/loras", response_model=AdminLoraItem, status_code=status.HTTP_201_CREATED)
async def create_lora(
    data: CreateLoraRequest,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> AdminLoraItem:
    try:
        row = await service.create_lora(
            name=data.name,
            description=data.description,
            preview_urls=data.preview_urls,
            is_nsfw=data.is_nsfw,
        )
    except CatalogConflictError as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
    response = await service.lora_response(row.id)
    if response is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "LoRA was not stored")
    return response


@router.patch("/loras/{lora_id}", response_model=AdminLoraItem)
async def update_lora(
    lora_id: UUID,
    data: UpdateLoraRequest,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> AdminLoraItem:
    try:
        row = await service.update_lora(lora_id, data.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise _invalid(exc) from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LoRA not found")
    response = await service.lora_response(lora_id)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LoRA not found")
    return response


@router.delete("/loras/{lora_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lora(
    lora_id: UUID,
    admin: CurrentAdminDep,
    service: AdminCatalogServiceDep,
) -> Response:
    try:
        deleted = await service.delete_lora(lora_id)
    except CatalogConflictError as exc:
        raise _conflict(exc) from exc
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LoRA not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
