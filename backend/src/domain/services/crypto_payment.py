import base64
import hmac
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from logging import getLogger
from typing import Any
from uuid import UUID

import httpx

from domain.entities.payment import Payment
from domain.enums import PaymentProvider, PaymentStatus
from domain.exceptions import ValidationError
from domain.exceptions.payments import (
    InvalidPaymentSignatureError,
    InvalidPaymentStateError,
    PaymentProviderError,
)
from domain.services.payment import PaymentService
from domain.services.referral import ReferralService
from domain.validators import NumberValidator, PaymentAmountValidator, TextValidator
from ports.repositories.payment import (
    PaymentRepositoryInterface,
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.user import UserRepositoryInterface

logger = getLogger(__name__)


class CryptoPaymentService(PaymentService):
    def __init__(
        self,
        payments: PaymentRepositoryInterface,
        wallets: WalletRepositoryInterface,
        transactions: TransactionRepositoryInterface,
        users: UserRepositoryInterface,
        client: httpx.AsyncClient,
        *,
        merchant_id: str,
        api_secret: str,
        invoice_ttl: timedelta = timedelta(hours=1),
        timeout: float = 10,
        referrals: ReferralService | None = None,
        postback_url: str = "",
    ) -> None:
        super().__init__(
            payments,
            wallets,
            transactions,
            users,
            PaymentProvider.ATLOS,
            invoice_ttl=invoice_ttl,
            referrals=referrals,
        )
        self._client = client
        self._merchant_id = TextValidator.validate(
            merchant_id, max_length=255, strip=True
        )
        self._api_secret = TextValidator.validate(api_secret, max_length=4096)
        self._timeout = NumberValidator.validate(timeout, min_value=0.1)
        self._postback_url = (
            TextValidator.validate(postback_url, max_length=2048)
            if postback_url
            else None
        )

    async def create_invoice(
        self,
        user_id: UUID,
        *,
        credits: int,
        amount: Decimal | int,
        currency: str = "USD",
        idempotency_key: str,
        memo: str = "Credits",
    ) -> Payment:
        memo = TextValidator.validate(memo, max_length=255)
        if currency == "XTR":
            raise InvalidPaymentStateError("XTR is reserved for Telegram Stars")
        payment = await self._prepare_payment(
            user_id,
            credits=credits,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
        )
        if payment.checkout_url is not None or payment.status != PaymentStatus.PENDING:
            return payment
        if self._is_expired(payment):
            raise InvalidPaymentStateError("invoice has expired")
        deadline = payment.expires_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        payload: dict[str, Any] = {
            "MerchantId": self._merchant_id,
            "OrderId": str(payment.id),
            "OrderAmount": payment.amount,
            "OrderCurrency": payment.currency,
            "Memo": memo,
            "TimeExpire": self._utc(deadline).isoformat(),
            "SendEmail": False,
        }
        if self._postback_url:
            payload["PostbackUrl"] = self._postback_url
        data = await self._request("Invoice/Create", payload)
        invoice_id = TextValidator.validate(data.get("Id"), max_length=255)
        checkout_url = self._checkout_url(data.get("PaymentLink"))
        return await self._payments.save(
            replace(payment, provider_invoice_id=invoice_id, checkout_url=checkout_url)
        )

    async def handle_postback(self, body: bytes, signature: str) -> bool:
        if not isinstance(body, bytes) or not isinstance(signature, str):
            raise InvalidPaymentSignatureError()
        expected = base64.b64encode(
            hmac.digest(self._api_secret.encode(), body, "sha256")
        )
        if not hmac.compare_digest(expected, signature.encode("utf-8")):
            raise InvalidPaymentSignatureError()
        try:
            data = json.loads(body, parse_float=Decimal)
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidPaymentStateError("invalid postback JSON") from exc
        return await self._apply_transaction(data)

    async def reconcile(
        self, *, since: datetime, until: datetime | None = None, page_size: int = 100
    ) -> int:
        since = self._utc(since)
        until = self._utc(until or datetime.now(UTC))
        if since > until:
            raise ValueError("since must not be later than until")
        NumberValidator.validate_integer(page_size, min_value=1, max_value=500)
        credited = 0
        offset = 0
        while True:
            data = await self._request(
                "Transaction/List",
                {
                    "MerchantId": self._merchant_id,
                    "TimeStart": since.isoformat(),
                    "TimeFinish": until.isoformat(),
                    "Skip": offset,
                    "Take": page_size,
                },
            )
            rows = data.get("Transactions")
            total = data.get("TotalCount")
            if not isinstance(rows, list) or type(total) is not int or total < 0:
                raise PaymentProviderError("ATLOS returned invalid transactions")
            for row in rows:
                try:
                    async with self._payments.settlement_scope():
                        applied = await self._apply_transaction(row)
                except ValidationError:
                    logger.exception(
                        "Skipping invalid ATLOS reconciliation transaction"
                    )
                else:
                    credited += applied
            offset += len(rows)
            if offset >= total:
                return credited
            if not rows:
                raise PaymentProviderError(
                    "ATLOS returned an incomplete transaction page"
                )

    async def _apply_transaction(self, data: Any) -> bool:
        if not isinstance(data, dict) or data.get("MerchantId") != self._merchant_id:
            raise InvalidPaymentStateError("unexpected ATLOS merchant")
        if type(data.get("Status")) is not int or data["Status"] != 100:
            return False
        try:
            ident = UUID(data["OrderId"])
        except KeyError, ValueError, TypeError, AttributeError:
            return False
        payment = await self._find_payment(ident)
        if payment is None:
            return False
        order_amount = self._amount(data.get("OrderAmount"))
        if (
            data.get("OrderCurrency") != payment.currency
            or order_amount != payment.amount
        ):
            raise InvalidPaymentStateError("ATLOS order details do not match")
        transaction_id = data.get("TransactionId", data.get("Id"))
        paid_amount = self._amount(data.get("PaidAmount"))
        try:
            paid_at = datetime.fromisoformat(data["TimeSent"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidPaymentStateError("invalid ATLOS payment timestamp") from exc
        details = {
            "asset_code": data.get("Asset", data.get("AssetCode")),
            "blockchain_code": data.get("Blockchain", data.get("BlockchainCode")),
            "asset_amount": self._amount(data.get("Amount")),
            "asset_fee": self._amount(data.get("Fee"), allow_zero=True),
            "blockchain_hash": TextValidator.validate(
                data.get("BlockchainHash"), max_length=255
            ),
            "sender_address": TextValidator.validate(
                data.get("UserWallet", data.get("SenderAddress")),
                max_length=255,
                nullable=True,
            ),
        }
        if details["asset_code"] is None or details["blockchain_code"] is None:
            raise InvalidPaymentStateError("missing ATLOS asset or blockchain")
        return await self._credit_payment(
            payment,
            transaction_id=transaction_id,
            paid_amount=paid_amount,
            paid_at=paid_at,
            details=details,
        )

    @staticmethod
    def _amount(value: object, *, allow_zero: bool = False) -> Decimal:
        if isinstance(value, str):
            try:
                value = Decimal(value)
            except InvalidOperation as exc:
                raise InvalidPaymentStateError("invalid ATLOS amount") from exc
        return PaymentAmountValidator.validate(value, allow_zero=allow_zero)

    async def _request(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        # ATLOS expects JSON numbers; preserve Decimal without converting to float.
        body = (
            "{"
            + ",".join(
                f"{json.dumps(key)}:{format(value, 'f') if isinstance(value, Decimal) else json.dumps(value)}"
                for key, value in payload.items()
            )
            + "}"
        )
        try:
            response = await self._client.post(
                f"https://api.atlos.io/gateway/rest/{operation}",
                headers={
                    "ApiSecret": self._api_secret,
                    "Content-Type": "application/json",
                },
                content=body,
                timeout=self._timeout,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentProviderError("ATLOS request failed") from exc
        try:
            data = json.loads(response.content, parse_float=Decimal)
        except ValueError as exc:
            raise PaymentProviderError("ATLOS returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise PaymentProviderError("ATLOS returned an invalid response")
        return data
