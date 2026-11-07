import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_system_settings"
down_revision = "0005_generation_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(
                sa.JSON(), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(key)) BETWEEN 1 AND 100 AND length(key) <= 100",
            name="check_system_settings_key_length",
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 500",
            name="check_system_settings_description_length",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
