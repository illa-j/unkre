from alembic import op

revision = "0008_stars_optional_payer"
down_revision = "0007_workflow_generation_credits"
branch_labels = None
depends_on = None

CONSTRAINT = "check_payments_provider_details"
NEW_DETAILS = (
    "(provider = 'telegram_stars' AND currency = 'XTR' "
    "AND amount = round(amount, 0) "
    "AND (telegram_user_id IS NULL OR telegram_user_id > 0) "
    "AND asset_code IS NULL AND blockchain_code IS NULL "
    "AND asset_amount IS NULL AND asset_fee IS NULL "
    "AND blockchain_hash IS NULL AND sender_address IS NULL) "
    "OR (provider = 'atlos' AND currency <> 'XTR' "
    "AND telegram_user_id IS NULL)"
)
OLD_DETAILS = (
    "(provider = 'telegram_stars' AND currency = 'XTR' "
    "AND amount = round(amount, 0) "
    "AND telegram_user_id IS NOT NULL AND telegram_user_id > 0 "
    "AND asset_code IS NULL AND blockchain_code IS NULL "
    "AND asset_amount IS NULL AND asset_fee IS NULL "
    "AND blockchain_hash IS NULL AND sender_address IS NULL) "
    "OR (provider = 'atlos' AND currency <> 'XTR' "
    "AND telegram_user_id IS NULL)"
)


def _is_postgres() -> bool:
    # SQLite cannot alter a CHECK constraint without rebuilding the whole table.
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return
    op.drop_constraint(CONSTRAINT, "payments", type_="check")
    op.create_check_constraint(CONSTRAINT, "payments", NEW_DETAILS)


def downgrade() -> None:
    if not _is_postgres():
        return
    op.drop_constraint(CONSTRAINT, "payments", type_="check")
    op.create_check_constraint(CONSTRAINT, "payments", OLD_DETAILS)
