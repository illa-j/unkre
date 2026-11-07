"""Workflow responses enriched with per-model recommended LoRA strengths."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from adapters.api.schemas.workflow import WorkflowResponse
from adapters.database.models import WorkflowModel


def workflow_responses(
    workflows: Sequence[WorkflowModel],
    strengths: Mapping[tuple[UUID, UUID], float],
) -> list[WorkflowResponse]:
    responses = []
    for workflow in workflows:
        recommended = {
            lora.id: strengths[(workflow.id, lora.id)]
            for lora in workflow.loras
            if (workflow.id, lora.id) in strengths
        }
        responses.append(
            WorkflowResponse.model_validate(workflow).model_copy(
                update={"recommended_strengths": recommended}
            )
        )
    return responses
