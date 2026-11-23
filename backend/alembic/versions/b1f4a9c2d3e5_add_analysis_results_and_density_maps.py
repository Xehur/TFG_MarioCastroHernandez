"""add analysis_results and density_maps

Revision ID: b1f4a9c2d3e5
Revises: 25cb5e511605
Create Date: 2026-07-01 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f4a9c2d3e5'
down_revision: Union[str, None] = '25cb5e511605'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('image_id', sa.Integer(), nullable=False),
        sa.Column('analysis_type', sa.String(), nullable=False),
        sa.Column('result_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_analysis_results_id'), 'analysis_results', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_analysis_results_image_id'),
        'analysis_results', ['image_id'], unique=False
    )
    op.create_index(
        op.f('ix_analysis_results_analysis_type'),
        'analysis_results', ['analysis_type'], unique=False
    )

    op.create_table(
        'density_maps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('image_id', sa.Integer(), nullable=False),
        sa.Column('grid_size', sa.Integer(), nullable=False),
        sa.Column('density_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_density_maps_id'), 'density_maps', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_density_maps_image_id'),
        'density_maps', ['image_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_density_maps_image_id'), table_name='density_maps')
    op.drop_index(op.f('ix_density_maps_id'), table_name='density_maps')
    op.drop_table('density_maps')
    op.drop_index(
        op.f('ix_analysis_results_analysis_type'), table_name='analysis_results'
    )
    op.drop_index(
        op.f('ix_analysis_results_image_id'), table_name='analysis_results'
    )
    op.drop_index(op.f('ix_analysis_results_id'), table_name='analysis_results')
    op.drop_table('analysis_results')
