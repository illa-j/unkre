from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from adapters.api.dependencies.admin import AdminServiceDep, CurrentAdminDep
from adapters.api.dependencies.admin_panel import AdminPanelServiceDep, OwnerDep
from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.schemas.admin_panel import (
    AdjustCreditsRequest,
    AdjustCreditsResponse,
    AdminAccountItem,
    AdminAccountPage,
    AdminGenerationPage,
    AdminOverviewResponse,
    AdminPaymentPage,
    AdminRedemptionPage,
    AdminUserPage,
    CreateAdminRequest,
    UpdateUserRequest,
    UpdateUserResponse,
)
from adapters.api.schemas.workflow import WorkflowResponse
from adapters.api.workflow_view import workflow_responses
from adapters.database.repositiries import AdminPanelRepository, WorkflowRepository

router = APIRouter(prefix="/admins", tags=["admins"])

GENERATION_STATES = "^(pending|queued|processing|completed|failed|cancelled|timed_out)$"
PAYMENT_STATES = "^(pending|processing|succeeded|failed|expired|cancelled|refunded)$"


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_overview(
    admin: CurrentAdminDep, service: AdminPanelServiceDep
) -> AdminOverviewResponse:
    return await service.overview()


@router.get("/users", response_model=AdminUserPage)
async def get_users(
    admin: CurrentAdminDep,
    service: AdminPanelServiceDep,
    query: Annotated[str | None, Query(max_length=200)] = None,
    state: Annotated[str | None, Query(pattern="^(active|blocked)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserPage:
    return await service.users(query=query, status=state, limit=limit, offset=offset)


@router.patch("/users/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: UUID,
    data: UpdateUserRequest,
    admin: CurrentAdminDep,
    service: AdminPanelServiceDep,
) -> UpdateUserResponse:
    if not await service.set_blocked(user_id, data.is_blocked):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return UpdateUserResponse(user_id=user_id, is_blocked=data.is_blocked)


@router.post(
    "/users/{user_id}/credits",
    response_model=AdjustCreditsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def adjust_credits(
    user_id: UUID,
    data: AdjustCreditsRequest,
    admin: CurrentAdminDep,
    service: AdminPanelServiceDep,
) -> AdjustCreditsResponse:
    result = await service.adjust_credits(user_id, data.amount, data.description)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return result


@router.get("/generations", response_model=AdminGenerationPage)
async def get_generations(
    admin: CurrentAdminDep,
    service: AdminPanelServiceDep,
    state: Annotated[str | None, Query(pattern=GENERATION_STATES)] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminGenerationPage:
    return await service.generations(
        status=state, query=query, limit=limit, offset=offset
    )


@router.get("/payments", response_model=AdminPaymentPage)
async def get_payments(
    admin: CurrentAdminDep,
    service: AdminPanelServiceDep,
    state: Annotated[str | None, Query(pattern=PAYMENT_STATES)] = None,
    provider: Annotated[str | None, Query(pattern="^(atlos|telegram_stars)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminPaymentPage:
    return await service.payments(
        status=state, provider=provider, limit=limit, offset=offset
    )


@router.get(
    "/promo-codes/{promo_code_id}/redemptions", response_model=AdminRedemptionPage
)
async def get_promo_redemptions(
    promo_code_id: UUID,
    admin: CurrentAdminDep,
    service: AdminPanelServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminRedemptionPage:
    return await service.redemptions(promo_code_id, limit=limit, offset=offset)


@router.get("/workflows", response_model=list[WorkflowResponse])
async def get_workflows(
    admin: CurrentAdminDep,
    manager: DatabaseManagerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[WorkflowResponse]:
    repository = WorkflowRepository(manager)
    workflows = await repository.get_all(limit=limit, offset=offset)
    strengths = await repository.lora_strengths([workflow.id for workflow in workflows])
    return workflow_responses(workflows, strengths)


@router.get("/team", response_model=AdminAccountPage)
async def get_team(admin: OwnerDep, manager: DatabaseManagerDep) -> AdminAccountPage:
    rows = await AdminPanelRepository(manager).admins()
    return AdminAccountPage(
        items=[
            AdminAccountItem(
                id=row.id,
                username=row.username,
                is_owner=row.is_owner,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.post(
    "/team", response_model=AdminAccountItem, status_code=status.HTTP_201_CREATED
)
async def create_team_member(
    data: CreateAdminRequest,
    admin: OwnerDep,
    service: AdminServiceDep,
    manager: DatabaseManagerDep,
) -> AdminAccountItem:
    created = await service.create_admin(
        data.username, data.password, is_owner=data.is_owner
    )
    row = await AdminPanelRepository(manager).admin(created.id)
    if row is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Admin was not stored"
        )
    return AdminAccountItem(
        id=row.id, username=row.username, is_owner=row.is_owner, created_at=row.created_at
    )
