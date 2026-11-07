import sqlalchemy as sa
from alembic import op

revision = "0010_workflow_is_active"
down_revision = "0009_workflow_lora_strengths"
branch_labels = None
depends_on = None

# The Raw model was retired from the product; keep its rows for generation
# history but stop exposing it in the catalog.
RETIRED_WORKFLOW = "krea2_raw_t2image_api"


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
    )
    op.execute(
        sa.text("UPDATE workflows SET is_active = false WHERE name = :name").bindparams(
            name=RETIRED_WORKFLOW
        )
    )


def downgrade() -> None:
    op.drop_column("workflows", "is_active")
