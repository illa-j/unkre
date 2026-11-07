from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from adapters.database.models.base import Base
from adapters.database.types import Timestamp


class UserAuthChallengeModel(Base):
    __tablename__ = "user_auth_challenges"

    nonce_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[Timestamp] = mapped_column(index=True)

    __table_args__ = (
        CheckConstraint(
            "provider IN ('google', 'telegram')", name="check_auth_provider"
        ),
        CheckConstraint("length(nonce_hash) = 64", name="check_auth_nonce_hash_length"),
    )
