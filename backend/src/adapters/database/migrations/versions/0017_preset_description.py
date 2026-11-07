"""Add a short description to generation presets."""

import sqlalchemy as sa
from alembic import op

revision = "0017_preset_description"
down_revision = "0016_preset_saves"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("generation_presets") as batch:
        batch.add_column(
            sa.Column(
                "description",
                sa.String(length=1000),
                server_default="",
                nullable=False,
            )
        )
        batch.create_check_constraint(
            "check_generation_presets_description_length",
            "length(description) <= 1000",
        )


def downgrade() -> None:
    with op.batch_alter_table("generation_presets") as batch:
        batch.drop_constraint(
            "check_generation_presets_description_length",
            type_="check",
        )
        batch.drop_column("description")
