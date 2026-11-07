"""Add preset ownership, visibility and preview images."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_preset_library"
down_revision = "0012_lora_is_nsfw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgres = op.get_context().dialect.name == "postgresql"
    if postgres:
        op.add_column(
            "generation_presets",
            sa.Column(
                "type", sa.String(length=10), server_default="user", nullable=False
            ),
        )
        op.add_column(
            "generation_presets",
            sa.Column(
                "is_public", sa.Boolean(), server_default=sa.false(), nullable=False
            ),
        )
        op.add_column(
            "generation_presets",
            sa.Column(
                "preview_urls",
                postgresql.JSONB(),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
        op.alter_column("generation_presets", "user_id", nullable=True)
        op.create_index(
            "ix_generation_presets_is_public",
            "generation_presets",
            ["is_public"],
            unique=False,
        )
        op.create_check_constraint(
            "check_generation_presets_type",
            "generation_presets",
            "type IN ('user', 'admin')",
        )
        op.create_check_constraint(
            "check_generation_presets_owner_type",
            "generation_presets",
            "(type = 'user' AND user_id IS NOT NULL) "
            "OR (type = 'admin' AND user_id IS NULL)",
        )
        return

    with op.batch_alter_table("generation_presets") as batch:
        batch.add_column(
            sa.Column(
                "type", sa.String(length=10), server_default="user", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "is_public", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "preview_urls",
                sa.JSON(),
                server_default=sa.text("'[]'"),
                nullable=False,
            )
        )
        batch.alter_column("user_id", nullable=True)
        batch.create_check_constraint(
            "check_generation_presets_type",
            "type IN ('user', 'admin')",
        )
        batch.create_check_constraint(
            "check_generation_presets_owner_type",
            "(type = 'user' AND user_id IS NOT NULL) "
            "OR (type = 'admin' AND user_id IS NULL)",
        )
    op.create_index(
        "ix_generation_presets_is_public",
        "generation_presets",
        ["is_public"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_generation_presets_is_public", table_name="generation_presets")
    postgres = op.get_context().dialect.name == "postgresql"
    if postgres:
        op.drop_constraint(
            "check_generation_presets_owner_type",
            "generation_presets",
            type_="check",
        )
        op.drop_constraint(
            "check_generation_presets_type", "generation_presets", type_="check"
        )
        op.alter_column("generation_presets", "user_id", nullable=False)
        op.drop_column("generation_presets", "preview_urls")
        op.drop_column("generation_presets", "is_public")
        op.drop_column("generation_presets", "type")
        return

    with op.batch_alter_table("generation_presets") as batch:
        batch.drop_constraint(
            "check_generation_presets_owner_type", type_="check"
        )
        batch.drop_constraint("check_generation_presets_type", type_="check")
        batch.alter_column("user_id", nullable=False)
        batch.drop_column("preview_urls")
        batch.drop_column("is_public")
        batch.drop_column("type")
