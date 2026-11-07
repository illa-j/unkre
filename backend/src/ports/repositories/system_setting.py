from typing import Protocol
from uuid import UUID

from domain.entities.system_setting import SystemSetting


class SystemSettingRepositoryInterface(Protocol):
    async def get(self, key: str) -> SystemSetting | None: ...

    async def list(self) -> list[SystemSetting]: ...

    async def upsert(
        self,
        key: str,
        *,
        value: object,
        description: str | None,
        updated_by: UUID | None,
    ) -> SystemSetting: ...

    async def delete(self, key: str) -> bool: ...
