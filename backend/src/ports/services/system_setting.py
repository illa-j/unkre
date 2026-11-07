from typing import Protocol


class SystemSettingsServiceInterface(Protocol):
    async def get_int(self, key: str) -> int: ...
