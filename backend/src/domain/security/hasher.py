import hashlib
import hmac


class TokenManager:
    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def verify_token(plain_token: str, hashed_token: str) -> bool:
        return hmac.compare_digest(TokenManager.hash_token(plain_token), hashed_token)
