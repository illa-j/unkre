from abc import ABC, abstractmethod
from datetime import timedelta


class JwtProviderInterface(ABC):
    @abstractmethod
    def create_access_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        pass

    @abstractmethod
    def create_refresh_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        pass

    @abstractmethod
    def decode_access_token(self, token: str) -> dict:
        pass

    @abstractmethod
    def decode_refresh_token(self, token: str) -> dict:
        pass
