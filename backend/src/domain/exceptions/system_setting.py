
from domain.exceptions import ValidationError


class UnknownSystemSettingError(ValidationError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Unknown system setting '{key}'.")


class InvalidSystemSettingError(ValidationError):
    def __init__(self, key: str, reason: str) -> None:
        self.key = key
        super().__init__(f"Invalid system setting '{key}': {reason}.")
