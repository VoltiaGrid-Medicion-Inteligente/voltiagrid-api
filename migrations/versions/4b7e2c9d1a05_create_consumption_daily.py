"""create consumption_daily (US-47, T-47.2)

Revision ID: 4b7e2c9d1a05
Revises: cb10f7277f53
Create Date: 2026-11-05 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4b7e2c9d1a05'
down_revision: Union[str, Sequence[str], None] = 'cb10f7277f53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Daily consumption per customer, day and band, read by the customer API."""
    op.create_table(
        'consumption_daily',
        sa.Column('customer_code', sa.String(length=30), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('band_name', sa.String(length=20), nullable=False),
        sa.Column('energy_kwh', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('cost', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('readings', sa.Integer(), nullable=False),
        sa.Column('estimated_readings', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['customer_code'], ['customer.code'],
                                name=op.f('fk_consumption_daily_customer_code_customer')),
        sa.PrimaryKeyConstraint('customer_code', 'date', 'band_name', name=op.f('pk_consumption_daily')),
    )


def downgrade() -> None:
    op.drop_table('consumption_daily')
