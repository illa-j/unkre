import sqlalchemy as sa
from alembic import op

revision = "0011_telegram_profile_flags"
down_revision = "0010_workflow_is_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_premium", sa.Boolean(), nullable=True))
    op.add_column(
        "users", sa.Column("allows_write_to_pm", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "users", sa.Column("added_to_attachment_menu", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "added_to_attachment_menu")
    op.drop_column("users", "allows_write_to_pm")
    op.drop_column("users", "is_premium")
