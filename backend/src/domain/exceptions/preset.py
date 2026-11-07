import uuid

from domain.exceptions import ValidationError


class PresetNotFoundError(ValidationError):
    def __init__(self, preset_id: uuid.UUID) -> None:
        self.preset_id = preset_id
        super().__init__(f"Preset '{preset_id}' does not exist.")
