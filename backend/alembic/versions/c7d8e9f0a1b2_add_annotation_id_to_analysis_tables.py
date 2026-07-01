"""add annotation_id to analysis_results and density_maps

Revision ID: c7d8e9f0a1b2
Revises: b1f4a9c2d3e5
Create Date: 2026-07-01 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b1f4a9c2d3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'analysis_results',
        sa.Column('annotation_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f('ix_analysis_results_annotation_id'),
        'analysis_results', ['annotation_id'], unique=False
    )
    op.create_foreign_key(
        'fk_analysis_results_annotation_id',
        'analysis_results', 'annotations',
        ['annotation_id'], ['id'], ondelete='CASCADE'
    )

    op.add_column(
        'density_maps',
        sa.Column('annotation_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f('ix_density_maps_annotation_id'),
        'density_maps', ['annotation_id'], unique=False
    )
    op.create_foreign_key(
        'fk_density_maps_annotation_id',
        'density_maps', 'annotations',
        ['annotation_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_density_maps_annotation_id', 'density_maps', type_='foreignkey'
    )
    op.drop_index(
        op.f('ix_density_maps_annotation_id'), table_name='density_maps'
    )
    op.drop_column('density_maps', 'annotation_id')

    op.drop_constraint(
        'fk_analysis_results_annotation_id', 'analysis_results',
        type_='foreignkey'
    )
    op.drop_index(
        op.f('ix_analysis_results_annotation_id'),
        table_name='analysis_results'
    )
    op.drop_column('analysis_results', 'annotation_id')
