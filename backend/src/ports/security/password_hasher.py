from abc import ABC, abstractmethod


class PasswordHasherInterface(ABC):
    @abstractmethod
    def hash_password(self, password: str) -> str: ...

    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool: ...

    @abstractmethod
    def needs_rehash(self, hashed_password: str) -> bool: ...
