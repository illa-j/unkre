"""Mark LoRAs that contain NSFW material.

The flag lets the studio show an 18+ warning only on NSFW LoRAs instead of
labelling the whole product as adult-only.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_lora_is_nsfw"
down_revision = "0011_telegram_profile_flags"
branch_labels = None
depends_on = None

# LoRAs marked ``category: nsfw`` in the published manifests. Admins can
# change the flag later from the catalog panel.
NSFW_LORAS = (
    "NSFW Qwen by TheseAlpacas V2.safetensors",
    "Pornmaster_QI2.1_Breasts_Slider_V1.safetensors",
    "Qwen_2.1_Unlocked_V1.safetensors",
    "getphat-reality-nsfw.safetensors",
    "krea2-aio-nsfw.safetensors",
    "krea2-nsfw-v5.safetensors",
    "mystic-xxx.safetensors",
    "nsfw-helper-slider.safetensors",
    "nsfw-krea2-flux.safetensors",
    "nsfw-plus.safetensors",
    "nsfw-posture-v3.safetensors",
    "nsfw-unlocked.safetensors",
    "photoreal-betternudes.safetensors",
    "pornmaster-realism-slider.safetensors",
    "qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors",
    "realistic-nudes.safetensors",
)


def upgrade() -> None:
    op.add_column(
        "loras",
        sa.Column(
            "is_nsfw", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.execute(
        sa.text("UPDATE loras SET is_nsfw = true WHERE name IN :names").bindparams(
            sa.bindparam("names", expanding=True, value=list(NSFW_LORAS))
        )
    )


def downgrade() -> None:
    op.drop_column("loras", "is_nsfw")
