class AuthenticationError(ValueError):
    pass


class InvalidCredentialsError(AuthenticationError):
    pass


class UserBlockedError(AuthenticationError):
    pass


class AuthProviderUnavailableError(AuthenticationError):
    pass


class AuthProviderNotConfiguredError(AuthProviderUnavailableError):
    pass


class AuthenticationConflictError(AuthenticationError):
    pass


class AccountLinkConflictError(AuthenticationError):
    pass
