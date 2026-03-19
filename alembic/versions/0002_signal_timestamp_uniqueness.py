"""add signal uniqueness by symbol and timestamp

Revision ID: 0002_signal_timestamp_uniqueness
Revises: 0001_initial_schema
Create Date: 2026-03-19 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0002_signal_timestamp_uniqueness"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_signals_symbol_signal_timestamp",
        "signals",
        ["symbol_id", "signal_timestamp"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_signals_symbol_signal_timestamp", "signals", type_="unique")
