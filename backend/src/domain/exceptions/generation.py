import uuid

from domain.exceptions import ValidationError


class InvalidWorkflowError(ValidationError):
    pass


class GenerationNotFoundError(ValidationError):
    def __init__(self, generation_id: uuid.UUID) -> None:
        self.generation_id = generation_id
        super().__init__(f"Generation '{generation_id}' does not exist.")


class InvalidGenerationStateError(ValidationError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid generation state: {reason}.")


class InvalidGenerationImagesError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Generation images must be non-empty base64 strings.")


class UnsupportedReferenceImagesError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Reference images are only supported by Qwen Image 2.1.")


class TooManyReferenceImagesError(ValidationError):
    def __init__(self, limit: int) -> None:
        super().__init__(f"Use up to {limit} reference images.")


class InvalidLoraStrengthsError(ValidationError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid LoRA strengths: {reason}.")


class WorkflowNotFoundError(ValidationError):
    def __init__(self, workflow_id: uuid.UUID | None) -> None:
        self.workflow_id = workflow_id
        super().__init__(f"Workflow '{workflow_id}' does not exist.")


class WorkflowMismatchError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Workflow and workflow_id must refer to the same workflow.")


class LoraNotFoundError(ValidationError):
    def __init__(self, lora_id: uuid.UUID) -> None:
        self.lora_id = lora_id
        super().__init__(f"LoRA '{lora_id}' does not exist.")


class LoraNotInWorkflowError(ValidationError):
    def __init__(self, lora_id: uuid.UUID, workflow_id: uuid.UUID | None) -> None:
        self.lora_id = lora_id
        self.workflow_id = workflow_id
        super().__init__(
            f"LoRA '{lora_id}' is not available in workflow '{workflow_id}'."
        )


class InsufficientCreditsError(ValidationError):
    def __init__(self, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(
            f"Not enough credits: {required} required, {available} available."
        )


class InvalidPreviewUrlsError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Preview URLs must be a list of non-empty strings.")
