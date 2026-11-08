"""create dr_participation (US-44, T-44.4)

Revision ID: 9d2f6a1c3e87
Revises: 4b7e2c9d1a05
Create Date: 2026-11-05 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9d2f6a1c3e87'
down_revision: Union[str, Sequence[str], None] = '4b7e2c9d1a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Demand-response participation per event and customer, published by voltiagrid-data (jobs.publish_dr)."""
    op.create_table(
        'dr_participation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=40), nullable=False),
        sa.Column('customer_code', sa.String(length=30), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('start_ts', sa.DateTime(), nullable=False),
        sa.Column('end_ts', sa.DateTime(), nullable=False),
        sa.Column('baseline_kwh', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('actual_kwh', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('savings_kwh', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('savings_pct', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('incentive_paid', sa.Boolean(), nullable=False),
        sa.Column('incentive_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['customer_code'], ['customer.code'],
                                name=op.f('fk_dr_participation_customer_code_customer')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_dr_participation')),
        sa.UniqueConstraint('event_id', 'customer_code', name=op.f('uq_dr_participation_event_id')),
    )
    op.create_index('ix_dr_participation_customer_code_event_date', 'dr_participation',
                    ['customer_code', 'event_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_dr_participation_customer_code_event_date', table_name='dr_participation')
    op.drop_table('dr_participation')
