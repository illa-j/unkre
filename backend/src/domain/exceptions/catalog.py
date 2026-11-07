from domain.exceptions.validation import ValidationError


class CatalogConflictError(ValidationError):
    pass


class WorkflowNameConflictError(CatalogConflictError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Workflow '{name}' already exists.")


class WorkflowHasHistoryError(CatalogConflictError):
    def __init__(self, generations: int, presets: int) -> None:
        super().__init__(
            "This model has generations or presets; deactivate it instead of deleting."
            f" (generations: {generations}, presets: {presets})"
        )


class LoraNameConflictError(CatalogConflictError):
    def __init__(self, name: str) -> None:
        super().__init__(f"LoRA '{name}' already exists.")


class LoraInUseError(CatalogConflictError):
    def __init__(self, count: int) -> None:
        super().__init__(
            f"This LoRA is used by {count} model(s); remove it from them first."
        )
