"""add auth fields to users

Revision ID: aefc933e87c6
Revises: 22ec54c35146
Create Date: 2026-06-24 16:38:37.836522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aefc933e87c6'
down_revision: Union[str, None] = '22ec54c35146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('hashed_password', sa.String(), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'hashed_password')
