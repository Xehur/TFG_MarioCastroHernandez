"""El nombre de imagen pasa a ser único por usuario, no global

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-11-12 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Índice único global -> índice normal + restricción única (user_id, filename).
    op.drop_index(op.f("ix_images_filename"), table_name="images")
    op.create_index(op.f("ix_images_filename"), "images", ["filename"], unique=False)
    op.create_unique_constraint(
        "uq_images_user_filename", "images", ["user_id", "filename"]
    )


def downgrade() -> None:
    # Falla si ya hay nombres repetidos entre usuarios (habría que renombrarlos).
    op.drop_constraint("uq_images_user_filename", "images", type_="unique")
    op.drop_index(op.f("ix_images_filename"), table_name="images")
    op.create_index(op.f("ix_images_filename"), "images", ["filename"], unique=True)
