from enum import StrEnum


class TransactionType(StrEnum):
    PURCHASE = "purchase"
    SPEND = "spend"
    REVERSAL = "reversal"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
