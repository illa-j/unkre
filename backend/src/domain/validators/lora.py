from domain.exceptions import InvalidLoraStrengthsError
from domain.validators.number import NumberValidator

MIN_LORA_STRENGTH = 0
MAX_LORA_STRENGTH = 2


def validate_lora_strength(value: object) -> int | float:
    """Validate a LoRA strength in the interval ``[0, 2]``."""
    strength = NumberValidator.validate(value, min_value=MIN_LORA_STRENGTH)
    if strength > MAX_LORA_STRENGTH:
        raise InvalidLoraStrengthsError(
            f"strength must be at least {MIN_LORA_STRENGTH} "
            f"and at most {MAX_LORA_STRENGTH}"
        )
    return strength
