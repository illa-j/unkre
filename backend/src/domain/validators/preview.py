from collections.abc import Sequence
from urllib.parse import urlparse
from uuid import UUID

from domain.exceptions import ValidationError
from domain.validators.text import TextValidator

MAX_PREVIEW_URLS = 20
MAX_PREVIEW_URL_LENGTH = 2048


def validate_preview_urls(
    values: Sequence[str], *, max_items: int = MAX_PREVIEW_URLS
) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValidationError("preview_urls must be a list")
    if len(values) > max_items:
        raise ValidationError(f"At most {max_items} preview images are allowed")
    urls: list[str] = []
    for value in values:
        url = TextValidator.validate(
            value, min_length=1, max_length=MAX_PREVIEW_URL_LENGTH, strip=True
        )
        internal_prefixes = (
            "/api/presets/previews/",
            "/api/loras/previews/",
        )
        for prefix in internal_prefixes:
            if url.startswith(prefix):
                try:
                    UUID(url.removeprefix(prefix))
                except ValueError as exc:
                    raise ValidationError(
                        "Uploaded preview URLs must contain a preview UUID"
                    ) from exc
                urls.append(url)
                break
        else:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValidationError("Preview URLs must be absolute http(s) URLs")
            urls.append(url)

    return urls
