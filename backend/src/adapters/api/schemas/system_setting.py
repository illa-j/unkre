from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from adapters.api.schemas.common import RequestModel, ResponseModel


class SystemSettingResponse(ResponseModel):
    key: str
    value: Any
    default: Any
    description: str
    source: Literal["default", "database"]
    updated_by: UUID | None = None
    updated_at: datetime | None = None


class UpdateSystemSettingRequest(RequestModel):
    value: Any
