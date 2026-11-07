import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_owner", sa.Boolean(), nullable=False),
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
            "length(hashed_password) BETWEEN 1 AND 255",
            name="check_admin_hashed_password_length",
        ),
        sa.CheckConstraint(
            "length(trim(username)) BETWEEN 2 AND 100 AND length(username) <= 100",
            name="check_admin_username_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admins_username"), "admins", ["username"], unique=True)
    op.create_table(
        "loras",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=4096), nullable=True),
        sa.Column(
            "preview_urls",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
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
            "json_type(preview_urls) = 'array'", name="check_loras_preview_urls_array"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "jsonb_typeof(preview_urls) = 'array'",
            name="check_loras_preview_urls_array",
        ).ddl_if(dialect="postgresql"),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 4096",
            name="check_loras_description_length",
        ),
        sa.CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 255 AND length(name) <= 255",
            name="check_loras_name_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_loras_name"), "loras", ["name"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column("google_email", sa.String(length=320), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=True),
        sa.Column("photo_url", sa.String(length=512), nullable=True),
        sa.Column(
            "referral_code",
            sa.String(length=24),
            server_default=sa.text(
                "substr(replace(CAST(gen_random_uuid() AS TEXT), '-', ''), 1, 24)"
            ),
            nullable=False,
        ),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
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
            "google_email IS NULL OR (length(trim(google_email)) BETWEEN 1 AND 320 AND length(google_email) <= 320)",
            name="check_users_google_email_length",
        ),
        sa.CheckConstraint(
            "google_sub IS NULL OR (length(google_sub) BETWEEN 1 AND 255)",
            name="check_users_google_sub_length",
        ),
        sa.CheckConstraint(
            "language_code IS NULL OR (length(trim(language_code)) BETWEEN 1 AND 10 AND length(language_code) <= 10)",
            name="check_users_language_code_length",
        ),
        sa.CheckConstraint(
            "last_name IS NULL OR (length(trim(last_name)) BETWEEN 1 AND 255 AND length(last_name) <= 255)",
            name="check_users_last_name_length",
        ),
        sa.CheckConstraint(
            "length(referral_code) = 24", name="check_users_referral_code_length"
        ),
        sa.CheckConstraint(
            "length(trim(first_name)) BETWEEN 1 AND 255 AND length(first_name) <= 255",
            name="check_users_first_name_length",
        ),
        sa.CheckConstraint(
            "photo_url IS NULL OR (length(photo_url) BETWEEN 1 AND 512)",
            name="check_users_photo_url_length",
        ),
        sa.CheckConstraint(
            "telegram_id IS NULL OR telegram_id BETWEEN 1 AND 9223372036854775807",
            name="check_users_telegram_id_range",
        ),
        sa.CheckConstraint(
            "username IS NULL OR (length(trim(username)) BETWEEN 1 AND 255 AND length(username) <= 255)",
            name="check_users_username_length",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referral_code"),
    )
    op.create_index(op.f("ix_users_first_name"), "users", ["first_name"], unique=False)
    op.create_index(
        op.f("ix_users_google_email"), "users", ["google_email"], unique=False
    )
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)
    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=4096), nullable=True),
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
            "description IS NULL OR length(description) <= 4096",
            name="check_workflows_description_length",
        ),
        sa.CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 255 AND length(name) <= 255",
            name="check_workflows_name_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflows_name"), "workflows", ["name"], unique=False)
    op.create_table(
        "admin_refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("_hashed_token", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("id > 0", name="check_admin_refresh_tokens_id_positive"),
        sa.CheckConstraint(
            "length(_hashed_token) BETWEEN 1 AND 100",
            name="check_admin_refresh_tokens_hashed_token_length",
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("_hashed_token"),
    )
    op.create_index(
        op.f("ix_admin_refresh_tokens_admin_id"),
        "admin_refresh_tokens",
        ["admin_id"],
        unique=False,
    )
    op.create_table(
        "generations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("prompt", sa.String(length=8192), nullable=False),
        sa.Column(
            "loras_strength",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "queued",
                "processing",
                "completed",
                "failed",
                "cancelled",
                "timed_out",
                name="generation_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "uploaded_images", sa.SmallInteger(), server_default="0", nullable=False
        ),
        sa.Column("seed", sa.BigInteger(), nullable=True),
        sa.Column("runpod_job_id", sa.String(length=255), nullable=True),
        sa.Column("runpod_endpoint_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.String(length=4096), nullable=True),
        sa.Column("credits_spent", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "json_type(loras_strength) = 'object'",
            name="check_generations_loras_strength_object",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "jsonb_typeof(loras_strength) = 'object'",
            name="check_generations_loras_strength_object",
        ).ddl_if(dialect="postgresql"),
        sa.CheckConstraint(
            "credits_spent IS NULL OR credits_spent BETWEEN 0 AND 2147483647",
            name="check_generations_credits_spent_range",
        ),
        sa.CheckConstraint(
            "error IS NULL OR length(error) <= 4096",
            name="check_generations_error_length",
        ),
        sa.CheckConstraint(
            "length(trim(prompt)) BETWEEN 1 AND 8192 AND length(prompt) <= 8192",
            name="check_generations_prompt_length",
        ),
        sa.CheckConstraint(
            "runpod_endpoint_id IS NULL OR length(trim(runpod_endpoint_id)) BETWEEN 1 AND 255 AND length(runpod_endpoint_id) <= 255",
            name="check_generations_runpod_endpoint_id_length",
        ),
        sa.CheckConstraint(
            "runpod_job_id IS NULL OR length(trim(runpod_job_id)) BETWEEN 1 AND 255 AND length(runpod_job_id) <= 255",
            name="check_generations_runpod_job_id_length",
        ),
        sa.CheckConstraint(
            "seed IS NULL OR seed BETWEEN 0 AND 9223372036854775807",
            name="check_generations_seed_range",
        ),
        sa.CheckConstraint(
            "uploaded_images BETWEEN 0 AND 32767",
            name="check_generations_uploaded_images_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generations_runpod_job_id"),
        "generations",
        ["runpod_job_id"],
        unique=True,
    )
    op.create_index(
        "ix_generations_stats_active",
        "generations",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'queued', 'processing')"),
    )
    op.create_index(
        "ix_generations_retention",
        "generations",
        ["status", sa.text("COALESCE(completed_at, updated_at)")],
        unique=False,
    )
    op.create_index(
        "ix_generations_stats_created", "generations", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_generations_user_id"), "generations", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_generations_workflow_id"), "generations", ["workflow_id"], unique=False
    )
    op.create_table(
        "user_refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("_hashed_token", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("id > 0", name="check_user_refresh_tokens_id_positive"),
        sa.CheckConstraint(
            "length(_hashed_token) BETWEEN 1 AND 100",
            name="check_user_refresh_tokens_hashed_token_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("_hashed_token"),
    )
    op.create_index(
        op.f("ix_user_refresh_tokens_user_id"),
        "user_refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "wallets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
            "credits BETWEEN 0 AND 9223372036854775807",
            name="check_wallets_credits_range",
        ),
        sa.CheckConstraint(
            "version BETWEEN 1 AND 2147483647", name="check_wallets_version_range"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "workflow_loras",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("lora_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["lora_id"], ["loras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workflow_id", "lora_id"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "telegram_stars",
                "atlos",
                name="payment_provider",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "succeeded",
                "failed",
                "expired",
                "cancelled",
                "refunded",
                name="payment_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("credits", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("paid_amount", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("provider_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("provider_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_url", sa.String(length=2048), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=True),
        sa.Column("blockchain_code", sa.String(length=32), nullable=True),
        sa.Column("asset_amount", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("asset_fee", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("blockchain_hash", sa.String(length=255), nullable=True),
        sa.Column("sender_address", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
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
            "(provider = 'telegram_stars' AND currency = 'XTR' AND amount = round(amount, 0) AND telegram_user_id IS NOT NULL AND telegram_user_id > 0 AND asset_code IS NULL AND blockchain_code IS NULL AND asset_amount IS NULL AND asset_fee IS NULL AND blockchain_hash IS NULL AND sender_address IS NULL) OR (provider = 'atlos' AND currency <> 'XTR' AND telegram_user_id IS NULL)",
            name="check_payments_provider_details",
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND substr(currency, 1, 1) BETWEEN 'A' AND 'Z' AND substr(currency, 2, 1) BETWEEN 'A' AND 'Z' AND substr(currency, 3, 1) BETWEEN 'A' AND 'Z'",
            name="check_payments_currency",
        ),
        sa.CheckConstraint(
            "provider <> 'telegram_stars' OR paid_amount IS NULL OR paid_amount = amount",
            name="check_payments_stars_paid_amount",
        ),
        sa.CheckConstraint(
            "status NOT IN ('succeeded', 'refunded') OR (paid_at IS NOT NULL AND provider_transaction_id IS NOT NULL AND paid_amount IS NOT NULL AND paid_amount >= amount)",
            name="check_payments_success_details",
        ),
        sa.CheckConstraint(
            "amount > 0 AND amount <= 99999999999999999999.999999999999999999",
            name="check_payments_amount_range",
        ),
        sa.CheckConstraint(
            "asset_amount IS NULL OR (asset_amount > 0 AND asset_amount <= 99999999999999999999.999999999999999999)",
            name="check_payments_asset_amount_range",
        ),
        sa.CheckConstraint(
            "asset_amount IS NULL OR (asset_code IS NOT NULL AND blockchain_code IS NOT NULL)",
            name="check_payments_asset_details",
        ),
        sa.CheckConstraint(
            "asset_code IS NULL OR length(asset_code) BETWEEN 1 AND 32",
            name="check_payments_asset_code_length",
        ),
        sa.CheckConstraint(
            "asset_fee IS NULL OR (asset_amount IS NOT NULL AND asset_fee <= asset_amount)",
            name="check_payments_asset_fee_limit",
        ),
        sa.CheckConstraint(
            "asset_fee IS NULL OR (asset_fee BETWEEN 0 AND 99999999999999999999.999999999999999999)",
            name="check_payments_asset_fee_range",
        ),
        sa.CheckConstraint(
            "blockchain_code IS NULL OR length(blockchain_code) BETWEEN 1 AND 32",
            name="check_payments_blockchain_code_length",
        ),
        sa.CheckConstraint(
            "blockchain_hash IS NULL OR length(blockchain_hash) BETWEEN 1 AND 255",
            name="check_payments_blockchain_hash_length",
        ),
        sa.CheckConstraint(
            "checkout_url IS NULL OR length(checkout_url) BETWEEN 1 AND 2048",
            name="check_payments_checkout_url_length",
        ),
        sa.CheckConstraint(
            "credits BETWEEN 1 AND 9223372036854775807",
            name="check_payments_credits_range",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 255 AND length(idempotency_key) <= 255",
            name="check_payments_idempotency_key_length",
        ),
        sa.CheckConstraint(
            "paid_amount IS NULL OR (paid_amount > 0 AND paid_amount <= 99999999999999999999.999999999999999999)",
            name="check_payments_paid_amount_range",
        ),
        sa.CheckConstraint(
            "provider_invoice_id IS NULL OR length(provider_invoice_id) BETWEEN 1 AND 255",
            name="check_payments_invoice_id_length",
        ),
        sa.CheckConstraint(
            "provider_payment_id IS NULL OR length(provider_payment_id) BETWEEN 1 AND 255",
            name="check_payments_payment_id_length",
        ),
        sa.CheckConstraint(
            "provider_transaction_id IS NULL OR length(provider_transaction_id) BETWEEN 1 AND 255",
            name="check_payments_transaction_id_length",
        ),
        sa.CheckConstraint(
            "sender_address IS NULL OR length(sender_address) BETWEEN 1 AND 255",
            name="check_payments_sender_address_length",
        ),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "wallet_id", name="uq_payments_id_wallet"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint(
            "provider", "provider_invoice_id", name="uq_payments_provider_invoice"
        ),
        sa.UniqueConstraint(
            "provider", "provider_payment_id", name="uq_payments_provider_payment"
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payments_provider_transaction",
        ),
    )
    op.create_index(
        op.f("ix_payments_wallet_id"), "payments", ["wallet_id"], unique=False
    )
    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "succeeded",
                "failed",
                "cancelled",
                name="payment_refund_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=4096), nullable=False),
        sa.Column("error", sa.String(length=4096), nullable=True),
        sa.Column("atlos_payout_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("recipient_address", sa.String(length=255), nullable=True),
        sa.Column("blockchain_hash", sa.String(length=255), nullable=True),
        sa.Column("asset_amount", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("asset_fee", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status <> 'succeeded' OR completed_at IS NOT NULL",
            name="check_payment_refunds_completion",
        ),
        sa.CheckConstraint(
            "asset_amount IS NULL OR (asset_amount > 0 AND asset_amount <= 99999999999999999999.999999999999999999)",
            name="check_payment_refunds_asset_amount_range",
        ),
        sa.CheckConstraint(
            "asset_fee IS NULL OR asset_fee BETWEEN 0 AND 99999999999999999999.999999999999999999",
            name="check_payment_refunds_asset_fee_range",
        ),
        sa.CheckConstraint(
            "atlos_payout_invoice_id IS NULL OR length(atlos_payout_invoice_id) BETWEEN 1 AND 255",
            name="check_payment_refunds_atlos_invoice_length",
        ),
        sa.CheckConstraint(
            "blockchain_hash IS NULL OR length(blockchain_hash) BETWEEN 1 AND 255",
            name="check_payment_refunds_blockchain_hash_length",
        ),
        sa.CheckConstraint(
            "error IS NULL OR length(error) <= 4096",
            name="check_payment_refunds_error_length",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 255 AND length(idempotency_key) <= 255",
            name="check_payment_refunds_idempotency_key_length",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) BETWEEN 1 AND 4096 AND length(reason) <= 4096",
            name="check_payment_refunds_reason_length",
        ),
        sa.CheckConstraint(
            "recipient_address IS NULL OR length(recipient_address) BETWEEN 1 AND 255",
            name="check_payment_refunds_recipient_address_length",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "wallet_id"],
            ["payments.id", "payments.wallet_id"],
            name="fk_payment_refunds_payment_wallet",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("atlos_payout_invoice_id"),
        sa.UniqueConstraint("id", "wallet_id", name="uq_payment_refunds_id_wallet"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("payment_id"),
    )
    op.create_index(
        op.f("ix_payment_refunds_wallet_id"),
        "payment_refunds",
        ["wallet_id"],
        unique=False,
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "purchase",
                "spend",
                "reversal",
                "refund",
                "adjustment",
                name="transaction_type",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_before", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=4096), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("payment_refund_id", sa.Uuid(), nullable=True),
        sa.Column("generation_id", sa.UUID(), nullable=True),
        sa.Column("reverses_transaction_id", sa.Uuid(), nullable=True),
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
            "(type = 'purchase' AND amount > 0 AND payment_id IS NOT NULL AND payment_refund_id IS NULL AND reverses_transaction_id IS NULL) OR (type = 'spend' AND amount < 0 AND payment_id IS NULL AND payment_refund_id IS NULL AND reverses_transaction_id IS NULL) OR (type = 'reversal' AND amount > 0 AND reverses_transaction_id IS NOT NULL AND payment_id IS NULL AND payment_refund_id IS NULL) OR (type = 'refund' AND amount < 0 AND payment_refund_id IS NOT NULL AND payment_id IS NULL AND reverses_transaction_id IS NULL) OR (type = 'adjustment' AND payment_id IS NULL AND payment_refund_id IS NULL AND reverses_transaction_id IS NULL)",
            name="check_transactions_type_details",
        ),
        sa.CheckConstraint(
            "amount <> 0 AND amount BETWEEN -9223372036854775807 AND 9223372036854775807",
            name="check_transactions_amount_range",
        ),
        sa.CheckConstraint(
            "balance_after - balance_before = amount",
            name="check_transactions_balance_delta",
        ),
        sa.CheckConstraint(
            "balance_before BETWEEN 0 AND 9223372036854775807 AND balance_after BETWEEN 0 AND 9223372036854775807",
            name="check_transactions_balances_range",
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 4096",
            name="check_transactions_description_length",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 255 AND length(idempotency_key) <= 255",
            name="check_transactions_idempotency_key_length",
        ),
        sa.CheckConstraint(
            "reverses_transaction_id IS NULL OR reverses_transaction_id <> id",
            name="check_transactions_not_self_reversal",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["generations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "wallet_id"],
            ["payments.id", "payments.wallet_id"],
            name="fk_transactions_payment_wallet",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_refund_id", "wallet_id"],
            ["payment_refunds.id", "payment_refunds.wallet_id"],
            name="fk_transactions_refund_wallet",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_transaction_id", "wallet_id"],
            ["transactions.id", "transactions.wallet_id"],
            name="fk_transactions_reversal_wallet",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "wallet_id", name="uq_transactions_id_wallet"),
        sa.UniqueConstraint("payment_id"),
        sa.UniqueConstraint("payment_refund_id"),
        sa.UniqueConstraint("reverses_transaction_id"),
        sa.UniqueConstraint(
            "wallet_id", "idempotency_key", name="uq_transactions_wallet_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_transactions_generation_id"),
        "transactions",
        ["generation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_wallet_id"), "transactions", ["wallet_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_wallet_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_generation_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_payment_refunds_wallet_id"), table_name="payment_refunds")
    op.drop_table("payment_refunds")
    op.drop_index(op.f("ix_payments_wallet_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_table("workflow_loras")
    op.drop_table("wallets")
    op.drop_index(
        op.f("ix_user_refresh_tokens_user_id"), table_name="user_refresh_tokens"
    )
    op.drop_table("user_refresh_tokens")
    op.drop_index(op.f("ix_generations_workflow_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_user_id"), table_name="generations")
    op.drop_index("ix_generations_retention", table_name="generations")
    op.drop_index("ix_generations_stats_created", table_name="generations")
    op.drop_index(
        "ix_generations_stats_active",
        table_name="generations",
        postgresql_where=sa.text("status IN ('pending', 'queued', 'processing')"),
    )
    op.drop_index(op.f("ix_generations_runpod_job_id"), table_name="generations")
    op.drop_table("generations")
    op.drop_index(
        op.f("ix_admin_refresh_tokens_admin_id"), table_name="admin_refresh_tokens"
    )
    op.drop_table("admin_refresh_tokens")
    op.drop_index(op.f("ix_workflows_name"), table_name="workflows")
    op.drop_table("workflows")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_index(op.f("ix_users_google_email"), table_name="users")
    op.drop_index(op.f("ix_users_first_name"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_loras_name"), table_name="loras")
    op.drop_table("loras")
    op.drop_index(op.f("ix_admins_username"), table_name="admins")
    op.drop_table("admins")
    for name in (
        "transaction_type",
        "payment_refund_status",
        "payment_status",
        "payment_provider",
        "generation_status",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
