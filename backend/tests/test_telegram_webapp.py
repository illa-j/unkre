import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from domain.exceptions.auth import InvalidCredentialsError
from domain.security.telegram_webapp import verify_init_data

TOKEN = "123456:test-bot-token"
USER = {
    "id": 1506207095,
    "first_name": "Illia",
    "last_name": "D",
    "username": "illiao0",
    "language_code": "uk",
    "photo_url": "https://t.me/i/userpic/320/example.jpg",
    "is_premium": True,
    "allows_write_to_pm": False,
    "added_to_attachment_menu": True,
}


def init_data(user: dict | None = None, *, token: str = TOKEN, auth_date: datetime | None = None, tamper: bool = False) -> str:
    fields = {
        "auth_date": str(int((auth_date or datetime.now(UTC)).timestamp())),
        "query_id": "AAHdF6IQAAAAAN0Xoha",
        "user": json.dumps(user or USER, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if tamper:
        fields["user"] = json.dumps({**USER, "id": 999}, separators=(",", ":"))
    return urlencode(fields)


def test_valid_init_data_returns_the_telegram_identity():
    verified = verify_init_data(init_data(), TOKEN)

    assert verified.telegram_id == USER["id"]
    assert verified.first_name == "Illia"
    assert verified.last_name == "D"
    assert verified.username == "illiao0"
    assert verified.language_code == "uk"
    assert verified.photo_url == USER["photo_url"]
    assert verified.is_premium is True
    assert verified.allows_write_to_pm is False
    assert verified.added_to_attachment_menu is True


def test_tampered_payload_is_rejected():
    with pytest.raises(InvalidCredentialsError):
        verify_init_data(init_data(tamper=True), TOKEN)


def test_wrong_bot_token_is_rejected():
    with pytest.raises(InvalidCredentialsError):
        verify_init_data(init_data(), "999:another-token")


def test_expired_auth_date_is_rejected():
    stale = datetime.now(UTC) - timedelta(hours=2)
    with pytest.raises(InvalidCredentialsError):
        verify_init_data(init_data(auth_date=stale), TOKEN, ttl=timedelta(hours=1))


def test_fresh_auth_date_inside_the_window_is_accepted():
    recent = datetime.now(UTC) - timedelta(minutes=5)
    assert verify_init_data(init_data(auth_date=recent), TOKEN).telegram_id == USER["id"]


def test_missing_hash_and_unconfigured_bot_are_rejected():
    with pytest.raises(InvalidCredentialsError):
        verify_init_data("auth_date=1&user=%7B%7D", TOKEN)
    with pytest.raises(InvalidCredentialsError):
        verify_init_data(init_data(), "")


def test_malformed_user_payload_is_rejected():
    with pytest.raises(InvalidCredentialsError):
        verify_init_data(init_data({"id": 0, "first_name": "X"}), TOKEN)
    with pytest.raises(InvalidCredentialsError):
        verify_init_data(init_data({"id": 5}), TOKEN)
