from uuid import UUID

from adapters.api.schemas.common import Password, RequestModel, ResponseModel, Username


class AdminLoginRequest(RequestModel):
    username: Username
    password: Password


class AdminResponse(ResponseModel):
    id: UUID
    username: str
    is_owner: bool


class AdminSessionResponse(ResponseModel):
    admin: AdminResponse
    expires_in: int
