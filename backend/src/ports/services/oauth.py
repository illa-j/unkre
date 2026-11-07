from typing import Protocol

from domain.entities.auth import AuthProvider, SocialIdentity


class OAuthServiceInterface(Protocol):
    def client_id(self, provider: AuthProvider) -> str:
        ...

    async def verify(
        self, provider: AuthProvider, id_token: str, nonce: str
    ) -> SocialIdentity:
        ...
