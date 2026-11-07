import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import UUID, BigInteger, DateTime, Numeric, String
from sqlalchemy.orm import mapped_column

type UUIDPrimaryKey = Annotated[
    uuid.UUID, mapped_column(UUID, primary_key=True, default=uuid.uuid7)
]
type String255 = Annotated[str, mapped_column(String(255))]
type String4096 = Annotated[str, mapped_column(String(4096))]
type String8192 = Annotated[str, mapped_column(String(8192))]
type Timestamp = Annotated[datetime, mapped_column(DateTime(timezone=True))]

type CreditAmount = Annotated[int, mapped_column(BigInteger)]
type MoneyAmount = Annotated[Decimal, mapped_column(Numeric(38, 18))]
