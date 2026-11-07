"""Award referral credits after the first successful credit purchase."""

import sqlalchemy as sa
from alembic import op

revision = "0015_referral_rewarded_at"
down_revision = "0014_preset_favorites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "referrals",
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Referrals created before this migration were rewarded immediately at
    # signup. Mark them as already paid so they are never rewarded twice.
    op.execute(
        sa.text(
            "UPDATE referrals SET rewarded_at = updated_at "
            "WHERE rewarded_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("referrals", "rewarded_at")
