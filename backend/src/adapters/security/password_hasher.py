from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from ports.security import PasswordHasherInterface

password_hasher = PasswordHasher()


class Argon2PasswordHasher(PasswordHasherInterface):
    def hash_password(self, password: str) -> str:
        return password_hasher.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return password_hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHash):
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        return password_hasher.check_needs_rehash(hashed_password)


class PasswordSecurity:

    @staticmethod
    def hash_password(password: str) -> str:
        return password_hasher.hash(password)

    @staticmethod
    def verify_password(raw_password: str, hashed_password: str) -> bool:
        try:
            return password_hasher.verify(hashed_password, raw_password)
        except (VerifyMismatchError, InvalidHash):
            return False

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        return password_hasher.check_needs_rehash(hashed_password)
