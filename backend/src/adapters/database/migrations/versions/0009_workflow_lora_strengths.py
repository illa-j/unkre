import sqlalchemy as sa
from alembic import op

revision = "0009_workflow_lora_strengths"
down_revision = "0008_stars_optional_payer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_loras",
        sa.Column("recommended_strength", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_loras", "recommended_strength")
