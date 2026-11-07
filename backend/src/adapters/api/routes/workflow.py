from typing import Annotated

from fastapi import APIRouter, Query

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.user import CurrentUserDep
from adapters.api.schemas.workflow import WorkflowResponse
from adapters.api.workflow_view import workflow_responses
from adapters.database.repositiries import WorkflowRepository

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowResponse])
async def get_workflows(
    user: CurrentUserDep,
    manager: DatabaseManagerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[WorkflowResponse]:
    repository = WorkflowRepository(manager)
    workflows = await repository.get_all(
        limit=limit, offset=offset, active_only=True
    )
    strengths = await repository.lora_strengths([workflow.id for workflow in workflows])
    return workflow_responses(workflows, strengths)
