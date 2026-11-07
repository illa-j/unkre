"""Separate saved presets from likes."""

import sqlalchemy as sa
from alembic import op

revision = "0016_preset_saves"
down_revision = "0015_referral_rewarded_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preset_saves",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("preset_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["preset_id"], ["generation_presets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "preset_id"),
    )
    op.create_index(
        "ix_preset_saves_preset_id",
        "preset_saves",
        ["preset_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_preset_saves_preset_id", table_name="preset_saves")
    op.drop_table("preset_saves")
