import sqlalchemy as sa
from alembic import op

revision = "0003_referrals_promo_codes"
down_revision = "0002_user_auth_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("inviter_id", sa.UUID(), nullable=False),
        sa.Column("referred_user_id", sa.UUID(), nullable=False),
        sa.Column("inviter_credits", sa.BigInteger(), nullable=False),
        sa.Column("invitee_credits", sa.BigInteger(), nullable=False),
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
            "inviter_id <> referred_user_id",
            name="check_referrals_distinct_users",
        ),
        sa.CheckConstraint(
            "inviter_credits BETWEEN 0 AND 9223372036854775807",
            name="check_referrals_inviter_credits_range",
        ),
        sa.CheckConstraint(
            "invitee_credits BETWEEN 0 AND 9223372036854775807",
            name="check_referrals_invitee_credits_range",
        ),
        sa.CheckConstraint(
            "inviter_credits > 0 OR invitee_credits > 0",
            name="check_referrals_has_reward",
        ),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["referred_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_user_id"),
    )
    op.create_index(
        op.f("ix_referrals_inviter_id"), "referrals", ["inviter_id"], unique=False
    )

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("credits", sa.BigInteger(), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column(
            "redeemed_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
            "length(code) BETWEEN 3 AND 64",
            name="check_promo_codes_code_length",
        ),
        sa.CheckConstraint(
            "credits BETWEEN 1 AND 2147483647",
            name="check_promo_codes_credits_range",
        ),
        sa.CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions BETWEEN 1 AND 2147483647",
            name="check_promo_codes_max_redemptions_range",
        ),
        sa.CheckConstraint(
            "redeemed_count BETWEEN 0 AND 2147483647",
            name="check_promo_codes_redeemed_count_range",
        ),
        sa.CheckConstraint(
            "max_redemptions IS NULL OR redeemed_count <= max_redemptions",
            name="check_promo_codes_redemption_limit",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_promo_codes_code"), "promo_codes", ["code"], unique=True
    )

    op.create_table(
        "promo_redemptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("promo_code_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("credits", sa.BigInteger(), nullable=False),
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
            "credits BETWEEN 1 AND 9223372036854775807",
            name="check_promo_redemptions_credits_range",
        ),
        sa.ForeignKeyConstraint(
            ["promo_code_id"], ["promo_codes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "promo_code_id", "user_id", name="uq_promo_redemptions_code_user"
        ),
    )
    op.create_index(
        op.f("ix_promo_redemptions_promo_code_id"),
        "promo_redemptions",
        ["promo_code_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promo_redemptions_user_id"),
        "promo_redemptions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_promo_redemptions_user_id"), table_name="promo_redemptions"
    )
    op.drop_index(
        op.f("ix_promo_redemptions_promo_code_id"), table_name="promo_redemptions"
    )
    op.drop_table("promo_redemptions")
    op.drop_index(op.f("ix_promo_codes_code"), table_name="promo_codes")
    op.drop_table("promo_codes")
    op.drop_index(op.f("ix_referrals_inviter_id"), table_name="referrals")
    op.drop_table("referrals")
