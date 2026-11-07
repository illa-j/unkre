"""Validation of Telegram MiniApp initData.

Telegram signs the launch payload with an HMAC derived from the bot token:

    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    hash = HMAC_SHA256(key=secret_key, msg=data_check_string)

where ``data_check_string`` is every field except ``hash``, sorted by key and
joined with newlines. See
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from domain.exceptions.auth import InvalidCredentialsError
from domain.validators import NumberValidator, TextValidator

ALLOWED_CLOCK_SKEW = timedelta(seconds=60)


@dataclass(frozen=True, kw_only=True)
class TelegramWebAppUser:
    telegram_id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    photo_url: str | None = None
    is_premium: bool | None = None
    allows_write_to_pm: bool | None = None
    added_to_attachment_menu: bool | None = None
    auth_date: datetime


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    ttl: timedelta = timedelta(hours=1),
    now: datetime | None = None,
) -> TelegramWebAppUser:
    token = bot_token.strip()
    if not token:
        raise InvalidCredentialsError("Telegram MiniApp login is not configured")
    TextValidator.validate(init_data, max_length=16384)
    pairs = parse_qsl(init_data, keep_blank_values=True)
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InvalidCredentialsError("Duplicate MiniApp fields")
    received_hash = fields.pop("hash", "")
    if len(received_hash) != 64:
        raise InvalidCredentialsError("Invalid MiniApp signature")
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, expected):
        raise InvalidCredentialsError("Invalid MiniApp signature")

    try:
        raw_date = int(fields.get("auth_date", ""))
        auth_date = datetime.fromtimestamp(
            NumberValidator.validate_integer(raw_date, min_value=0), tz=UTC
        )
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise InvalidCredentialsError("Invalid MiniApp auth date") from exc
    moment = now or datetime.now(UTC)
    if auth_date > moment + ALLOWED_CLOCK_SKEW or moment - auth_date > ttl:
        raise InvalidCredentialsError("Expired MiniApp login")

    try:
        user = json.loads(fields.get("user", ""))
    except (TypeError, ValueError) as exc:
        raise InvalidCredentialsError("Invalid MiniApp user") from exc
    if not isinstance(user, dict):
        raise InvalidCredentialsError("Invalid MiniApp user")
    try:
        telegram_id = NumberValidator.validate_integer(user.get("id"), min_value=1)
        first_name = TextValidator.validate(
            user.get("first_name"), min_length=1, max_length=255, strip=True
        )
    except (ValueError, TypeError) as exc:
        raise InvalidCredentialsError("Invalid MiniApp user") from exc
    if telegram_id > 2**63 - 1:
        raise InvalidCredentialsError("Invalid MiniApp user")
    return TelegramWebAppUser(
        telegram_id=telegram_id,
        first_name=first_name,
        last_name=_optional_text(user.get("last_name"), 255),
        username=_optional_text(user.get("username"), 255),
        language_code=_optional_text(user.get("language_code"), 10),
        photo_url=_optional_text(user.get("photo_url"), 512),
        is_premium=_optional_bool(user.get("is_premium")),
        allows_write_to_pm=_optional_bool(user.get("allows_write_to_pm")),
        added_to_attachment_menu=_optional_bool(user.get("added_to_attachment_menu")),
        auth_date=auth_date,
    )


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_text(value: object, limit: int) -> str | None:
    if value is None or value == "":
        return None
    try:
        return TextValidator.validate(str(value), max_length=limit, strip=True)
    except ValueError:
        return None
