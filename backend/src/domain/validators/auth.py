from domain.validators.text import TextValidator


class AuthValidator:
    @staticmethod
    def validate_password_strength(password: str) -> str:
        return TextValidator.validate(password, min_length=8)
