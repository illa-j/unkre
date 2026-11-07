import sqlalchemy as sa
from alembic import op

revision = "0004_generation_negative_prompt"
down_revision = "0003_referrals_promo_codes"
branch_labels = None
depends_on = None


def _supports_check_alter() -> bool:
    # SQLite cannot ALTER TABLE ... ADD/DROP CONSTRAINT without recreating the
    # table, and the generations table has an expression-based index that
    # SQLite reflection cannot preserve. PostgreSQL is the production dialect.
    return op.get_bind().dialect.name != "sqlite"


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column(
            "negative_prompt",
            sa.String(length=8192),
            server_default="",
            nullable=False,
        ),
    )
    if _supports_check_alter():
        op.create_check_constraint(
            "check_generations_negative_prompt_length",
            "generations",
            "length(negative_prompt) <= 8192",
        )


def downgrade() -> None:
    if _supports_check_alter():
        op.drop_constraint(
            "check_generations_negative_prompt_length",
            "generations",
            type_="check",
        )
    op.drop_column("generations", "negative_prompt")
