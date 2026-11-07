"""Shared request/response primitives for the HTTP schemas.

The limits below mirror the ORM models (and their domain validators), so the
API rejects a payload for the same reasons the database would, and every
endpoint validates the same field the same way.
"""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# users.referral_code
REFERRAL_CODE_MAX = 64
# admins.username
USERNAME_MIN = 2
USERNAME_MAX = 100
# admins.hashed_password (raw passwords are bounded before hashing)
PASSWORD_MIN = 10
PASSWORD_MAX = 1024
# users.refresh_tokens / OAuth identity token
TOKEN_MAX = 16384
NONCE_MIN = 32
NONCE_MAX = 256
# generations.prompt / negative_prompt
PROMPT_MAX = 8192
# presets.name
PRESET_NAME_MAX = 100
# generation_presets.description
PRESET_DESCRIPTION_MAX = 1000
# promo_codes.code
PROMO_CODE_MIN = 3
PROMO_CODE_MAX = 64
# payments.idempotency_key
IDEMPOTENCY_KEY_MAX = 255
# generations.uploaded_images (SmallInteger)
MAX_REFERENCE_IMAGES = 32767
# generations.seed
SEED_MAX = 2**63 - 1
# payments.credits / wallets.credits stay within the signed 32-bit API surface
CREDITS_MAX = 2**31 - 1
# Manual ledger adjustments are bounded by the same wallet limits
ADJUSTMENT_MAX = CREDITS_MAX
# transactions.description
ADJUSTMENT_DESCRIPTION_MAX = 4096

Username = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=USERNAME_MIN, max_length=USERNAME_MAX
    ),
]
Password = Annotated[
    str, Field(strict=True, min_length=1, max_length=PASSWORD_MAX, repr=False)
]
StrongPassword = Annotated[
    str, Field(strict=True, min_length=PASSWORD_MIN, max_length=PASSWORD_MAX, repr=False)
]
Token = Annotated[str, Field(strict=True, min_length=1, max_length=TOKEN_MAX)]
Nonce = Annotated[
    str,
    StringConstraints(strict=True, min_length=NONCE_MIN, max_length=NONCE_MAX),
]
ReferralCode = Annotated[str, Field(strict=True, max_length=REFERRAL_CODE_MAX)]
Prompt = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=PROMPT_MAX
    ),
]
OptionalPrompt = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, max_length=PROMPT_MAX),
]
PresetName = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=PRESET_NAME_MAX
    ),
]
PresetDescription = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, max_length=PRESET_DESCRIPTION_MAX
    ),
]
PromoCodeInput = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=PROMO_CODE_MIN,
        max_length=PROMO_CODE_MAX,
    ),
]
IdempotencyKey = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=IDEMPOTENCY_KEY_MAX
    ),
]
ReferenceImage = Annotated[str, Field(strict=True, min_length=1)]
Seed = Annotated[int, Field(strict=True, ge=0, le=SEED_MAX)]
# LoRA strengths use the interval [0, 2].
LoraStrength = Annotated[
    float, Field(strict=True, allow_inf_nan=False, ge=0, le=2)
]
LoraStrengths = dict[UUID, LoraStrength]
CreditAmount = Annotated[int, Field(strict=True, ge=1, le=CREDITS_MAX)]
OptionalCreditAmount = Annotated[int, Field(strict=True, ge=1, le=CREDITS_MAX)] | None
AdjustmentAmount = Annotated[
    int, Field(strict=True, ge=-ADJUSTMENT_MAX, le=ADJUSTMENT_MAX)
]
AdjustmentDescription = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=3,
        max_length=ADJUSTMENT_DESCRIPTION_MAX,
    ),
]
GenerationCredits = Annotated[int, Field(strict=True, ge=0, le=CREDITS_MAX)]


class RequestModel(BaseModel):
    """Reject unknown fields instead of silently ignoring client mistakes."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    """Response bodies can be built from ORM rows or domain entities."""

    model_config = ConfigDict(from_attributes=True)


class Page[ItemT](ResponseModel):
    items: list[ItemT]
    total: int


class Collection[ItemT](ResponseModel):
    items: list[ItemT]


class PromptTuning(RequestModel):
    """Prompt settings shared by generation requests and presets."""

    negative_prompt: OptionalPrompt = ""
    loras_strength: LoraStrengths | None = None
    seed: Seed | None = None
