from pydantic import Field

from adapters.settings.base import BaseAppSettings


class AdminSettings(BaseAppSettings):
    """Bootstrap owner account created on API startup.

    The account is only created when both values are present and it does not
    exist yet, so restarts never overwrite an existing password.
    """

    ADMIN_NAME: str = ""
    ADMIN_PASSWORD: str = Field(default="", repr=False)

    @property
    def configured(self) -> bool:
        return bool(self.ADMIN_NAME.strip() and self.ADMIN_PASSWORD)
