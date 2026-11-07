"""Add server-side preset favorites for popularity sorting."""

import sqlalchemy as sa
from alembic import op

revision = "0014_preset_favorites"
down_revision = "0013_preset_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preset_favorites",
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
        "ix_preset_favorites_preset_id",
        "preset_favorites",
        ["preset_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_preset_favorites_preset_id", table_name="preset_favorites")
    op.drop_table("preset_favorites")
