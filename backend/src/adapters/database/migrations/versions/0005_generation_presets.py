import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_generation_presets"
down_revision = "0004_generation_negative_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_presets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("prompt", sa.String(length=8192), nullable=False),
        sa.Column(
            "negative_prompt",
            sa.String(length=8192),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "loras_strength",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(
                sa.JSON(), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("seed", sa.BigInteger(), nullable=True),
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
            "length(trim(name)) BETWEEN 1 AND 100 AND length(name) <= 100",
            name="check_generation_presets_name_length",
        ),
        sa.CheckConstraint(
            "length(prompt) <= 8192",
            name="check_generation_presets_prompt_length",
        ),
        sa.CheckConstraint(
            "length(negative_prompt) <= 8192",
            name="check_generation_presets_negative_prompt_length",
        ),
        sa.CheckConstraint(
            "seed IS NULL OR seed BETWEEN 0 AND 9223372036854775807",
            name="check_generation_presets_seed_range",
        ),
        sa.CheckConstraint(
            "json_type(loras_strength) = 'object'",
            name="check_generation_presets_loras_strength_object",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "jsonb_typeof(loras_strength) = 'object'",
            name="check_generation_presets_loras_strength_object",
        ).ddl_if(dialect="postgresql"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generation_presets_user_id"),
        "generation_presets",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_presets_workflow_id"),
        "generation_presets",
        ["workflow_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_generation_presets_workflow_id"),
        table_name="generation_presets",
    )
    op.drop_index(
        op.f("ix_generation_presets_user_id"), table_name="generation_presets"
    )
    op.drop_table("generation_presets")
