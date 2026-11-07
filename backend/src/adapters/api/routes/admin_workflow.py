from uuid import UUID

from fastapi import APIRouter

from adapters.api.dependencies.admin import CurrentAdminDep
from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.schemas.workflow import (
    UpdateWorkflowCreditsRequest,
    WorkflowResponse,
)
from adapters.api.workflow_view import workflow_responses
from adapters.database.repositiries import WorkflowRepository
from domain.exceptions.generation import WorkflowNotFoundError

router = APIRouter(prefix="/admins/workflows", tags=["admins"])


@router.patch("/{workflow_id}/credits", response_model=WorkflowResponse)
async def update_workflow_credits(
    workflow_id: UUID,
    data: UpdateWorkflowCreditsRequest,
    admin: CurrentAdminDep,
    manager: DatabaseManagerDep,
) -> WorkflowResponse:
    repository = WorkflowRepository(manager)
    updated = await repository.update(
        workflow_id, {"generation_credits": data.generation_credits}
    )
    if updated is None:
        raise WorkflowNotFoundError(workflow_id)
    strengths = await repository.lora_strengths([workflow_id])
    return workflow_responses([updated], strengths)[0]
