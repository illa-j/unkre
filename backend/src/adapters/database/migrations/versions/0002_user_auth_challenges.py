import sqlalchemy as sa
from alembic import op

revision = "0002_user_auth_challenges"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_auth_challenges",
        sa.Column("nonce_hash", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider IN ('google', 'telegram')", name="check_auth_provider"
        ),
        sa.CheckConstraint(
            "length(nonce_hash) = 64", name="check_auth_nonce_hash_length"
        ),
    )
    op.create_index(
        "ix_user_auth_challenges_expires_at", "user_auth_challenges", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_auth_challenges_expires_at", table_name="user_auth_challenges"
    )
    op.drop_table("user_auth_challenges")
