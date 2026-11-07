import sqlalchemy as sa
from alembic import op

revision = "0007_workflow_generation_credits"
down_revision = "0006_system_settings"
branch_labels = None
depends_on = None


def _supports_check_alter() -> bool:
    # SQLite cannot ALTER TABLE ... ADD CONSTRAINT without rebuilding the table.
    return op.get_bind().dialect.name != "sqlite"


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column(
            "generation_credits",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    if _supports_check_alter():
        op.create_check_constraint(
            "check_workflows_generation_credits_range",
            "workflows",
            "generation_credits BETWEEN 0 AND 2147483647",
        )


def downgrade() -> None:
    if _supports_check_alter():
        op.drop_constraint(
            "check_workflows_generation_credits_range",
            "workflows",
            type_="check",
        )
    op.drop_column("workflows", "generation_credits")
