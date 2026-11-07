from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from adapters.database.types import Timestamp


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[Timestamp] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Timestamp] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
