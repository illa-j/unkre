class InvalidTokenError(ValueError):
    pass


class TokenExpiredError(InvalidTokenError):
    pass
