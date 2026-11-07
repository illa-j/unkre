from domain.exceptions import ValidationError


class InvalidRepositoryFieldError(ValidationError):
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        super().__init__(f"Cannot update field '{field}': {reason}.")
