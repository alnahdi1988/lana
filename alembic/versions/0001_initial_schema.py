"""Initial platform schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


listed_exchange = postgresql.ENUM("NYSE", "NASDAQ", "NYSE_ARCA", "AMEX", name="listed_exchange", create_type=False)
market_data_source = postgresql.ENUM("POLYGON", name="market_data_source", create_type=False)
universe_refresh_session = postgresql.ENUM("PREMARKET", "POSTMARKET", "INTRADAY", name="universe_refresh_session", create_type=False)
universe_tier = postgresql.ENUM("TIER_1", "TIER_2", "TIER_3", name="universe_tier", create_type=False)
timeframe = postgresql.ENUM("5M", "15M", "1H", "4H", "1D", name="timeframe", create_type=False)
signal_value = postgresql.ENUM("LONG", "NONE", name="signal_value", create_type=False)
signal_grade = postgresql.ENUM("A+", "A", "B", "IGNORE", name="signal_grade", create_type=False)
htf_bias = postgresql.ENUM("BULLISH", "NEUTRAL", "BEARISH", name="htf_bias", create_type=False)
entry_type = postgresql.ENUM("AGGRESSIVE", "BASE", "CONFIRMATION", name="entry_type", create_type=False)
trail_mode = postgresql.ENUM("STRUCTURAL", "NONE", name="trail_mode", create_type=False)
evaluation_status = postgresql.ENUM("PENDING", "EVALUATING", "FINALIZED", "ERROR", name="evaluation_status", create_type=False)


def _timescaledb_available() -> bool:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb' LIMIT 1"
        )
    ).scalar()
    return bool(row)


def _timescaledb_installed() -> bool:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb' LIMIT 1"
        )
    ).scalar()
    return bool(row)


def upgrade() -> None:
    bind = op.get_bind()

    if _timescaledb_available():
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    listed_exchange.create(bind, checkfirst=True)
    market_data_source.create(bind, checkfirst=True)
    universe_refresh_session.create(bind, checkfirst=True)
    universe_tier.create(bind, checkfirst=True)
    timeframe.create(bind, checkfirst=True)
    signal_value.create(bind, checkfirst=True)
    signal_grade.create(bind, checkfirst=True)
    htf_bias.create(bind, checkfirst=True)
    entry_type.create(bind, checkfirst=True)
    trail_mode.create(bind, checkfirst=True)
    evaluation_status.create(bind, checkfirst=True)

    op.create_table(
        "symbols",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("polygon_ticker", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("exchange", listed_exchange, nullable=False),
        sa.Column("security_type", sa.String(length=32), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_etf", sa.Boolean(), nullable=False),
        sa.Column("is_otc", sa.Boolean(), nullable=False),
        sa.Column("last_reference_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("last_reference_price_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cik", sa.String(length=20), nullable=True),
        sa.Column("primary_listing", sa.String(length=64), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_symbols"),
        sa.UniqueConstraint("ticker", name="uq_symbols_ticker"),
        sa.UniqueConstraint("polygon_ticker", name="uq_symbols_polygon_ticker"),
    )

    op.create_table(
        "universe_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_session", universe_refresh_session, nullable=False),
        sa.Column("source", market_data_source, nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_universe_snapshots"),
        sa.UniqueConstraint(
            "snapshot_timestamp",
            "refresh_session",
            name="uq_universe_snapshots_snapshot_timestamp_session",
        ),
    )
    op.create_index("ix_universe_snapshots_snapshot_timestamp", "universe_snapshots", ["snapshot_timestamp"], unique=False)

    op.create_table(
        "universe_snapshot_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_ticker_cache", sa.String(length=16), nullable=True),
        sa.Column("hard_eligible", sa.Boolean(), nullable=False),
        sa.Column("tier", universe_tier, nullable=True),
        sa.Column("last_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("avg_daily_volume_20d", sa.Numeric(18, 2), nullable=True),
        sa.Column("avg_dollar_volume_20d", sa.Numeric(18, 2), nullable=True),
        sa.Column("sufficient_history", sa.Boolean(), nullable=False),
        sa.Column("data_quality_ok", sa.Boolean(), nullable=False),
        sa.Column("rejection_reasons", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["snapshot_id"], ["universe_snapshots.id"], name="fk_usm_snapshot_id_universe_snapshots", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], name="fk_usm_symbol_id_symbols", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_universe_snapshot_memberships"),
        sa.UniqueConstraint("snapshot_id", "symbol_id", name="uq_universe_snapshot_memberships_snapshot_symbol"),
    )
    op.create_index("ix_universe_snapshot_memberships_snapshot_id", "universe_snapshot_memberships", ["snapshot_id"], unique=False)
    op.create_index("ix_universe_snapshot_memberships_symbol_id", "universe_snapshot_memberships", ["symbol_id"], unique=False)

    op.create_table(
        "bars",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", timeframe, nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("high_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("low_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("vwap", sa.Numeric(12, 4), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("source", market_data_source, nullable=False),
        sa.Column("adjustment", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("high_price >= low_price", name="ck_bars_high_ge_low"),
        sa.CheckConstraint("volume >= 0", name="ck_bars_volume_non_negative"),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], name="fk_bars_symbol_id_symbols", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_bars"),
        sa.UniqueConstraint(
            "symbol_id",
            "timeframe",
            "bar_timestamp",
            "adjustment",
            name="uq_bars_symbol_timeframe_bar_timestamp_adjustment",
        ),
    )
    op.create_index("ix_bars_symbol_timeframe_known_at", "bars", ["symbol_id", "timeframe", "known_at"], unique=False)
    op.create_index("ix_bars_timeframe_bar_timestamp", "bars", ["timeframe", "bar_timestamp"], unique=False)
    if _timescaledb_installed():
        op.execute("SELECT create_hypertable('bars', 'bar_timestamp', if_not_exists => TRUE, migrate_data => TRUE)")

    op.create_table(
        "features",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timeframe", timeframe, nullable=True),
        sa.Column("feature_set", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.String(length=32), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], name="fk_features_symbol_id_symbols", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_features"),
        sa.UniqueConstraint(
            "symbol_id",
            "timeframe",
            "feature_set",
            "feature_version",
            "bar_timestamp",
            name="uq_features_symbol_timeframe_set_version_bar_timestamp",
        ),
    )
    op.create_index("ix_features_symbol_id", "features", ["symbol_id"], unique=False)
    op.create_index("ix_features_bar_timestamp", "features", ["bar_timestamp"], unique=False)
    op.create_index("ix_features_known_at", "features", ["known_at"], unique=False)

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("universe_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signal_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("htf_bar_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mtf_bar_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ltf_bar_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signal", signal_value, nullable=False),
        sa.Column("signal_version", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("grade", signal_grade, nullable=False),
        sa.Column("bias_htf", htf_bias, nullable=False),
        sa.Column("setup_state", sa.String(length=64), nullable=False),
        sa.Column("reason_codes", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("event_risk_blocked", sa.Boolean(), nullable=False),
        sa.Column("extensible_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_signals_confidence_between_zero_and_one"),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], name="fk_signals_symbol_id_symbols", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["universe_snapshot_id"], ["universe_snapshots.id"], name="fk_signals_universe_snapshot_id_universe_snapshots", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_signals"),
    )
    op.create_index("ix_signals_symbol_signal_timestamp", "signals", ["symbol_id", "signal_timestamp"], unique=False)
    op.create_index("ix_signals_known_at", "signals", ["known_at"], unique=False)
    op.create_index("ix_signals_signal", "signals", ["signal"], unique=False)
    op.create_index("ix_signals_grade", "signals", ["grade"], unique=False)
    op.create_index("ix_signals_bias_htf", "signals", ["bias_htf"], unique=False)
    op.create_index("ix_signals_setup_state", "signals", ["setup_state"], unique=False)

    op.create_table(
        "trade_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_type", entry_type, nullable=False),
        sa.Column("entry_zone_low", sa.Numeric(12, 4), nullable=False),
        sa.Column("entry_zone_high", sa.Numeric(12, 4), nullable=False),
        sa.Column("confirmation_level", sa.Numeric(12, 4), nullable=False),
        sa.Column("invalidation_level", sa.Numeric(12, 4), nullable=False),
        sa.Column("tp1", sa.Numeric(12, 4), nullable=False),
        sa.Column("tp2", sa.Numeric(12, 4), nullable=False),
        sa.Column("trail_mode", trail_mode, nullable=False),
        sa.Column("plan_reason_codes", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("extensible_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("entry_zone_low <= entry_zone_high", name="ck_trade_plans_entry_zone_low_le_high"),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], name="fk_trade_plans_signal_id_signals", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_trade_plans"),
        sa.UniqueConstraint("signal_id", name="uq_trade_plans_signal_id"),
    )
    op.create_index("ix_trade_plans_signal_id", "trade_plans", ["signal_id"], unique=False)
    op.create_index("ix_trade_plans_plan_timestamp", "trade_plans", ["plan_timestamp"], unique=False)
    op.create_index("ix_trade_plans_known_at", "trade_plans", ["known_at"], unique=False)

    op.create_table(
        "outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_status", evaluation_status, nullable=False),
        sa.Column("evaluation_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tracked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bars_tracked", sa.Integer(), nullable=False),
        sa.Column("first_barrier", sa.String(length=32), nullable=True),
        sa.Column("success_label", sa.Boolean(), nullable=True),
        sa.Column("tp2_label", sa.Boolean(), nullable=True),
        sa.Column("invalidated_first", sa.Boolean(), nullable=True),
        sa.Column("mfe_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("mae_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("bars_to_tp1", sa.Integer(), nullable=True),
        sa.Column("extensible_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], name="fk_outcomes_signal_id_signals", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_outcomes"),
        sa.UniqueConstraint("signal_id", name="uq_outcomes_signal_id"),
    )
    op.create_index("ix_outcomes_signal_id", "outcomes", ["signal_id"], unique=False)
    op.create_index("ix_outcomes_evaluation_status", "outcomes", ["evaluation_status"], unique=False)
    op.create_index("ix_outcomes_tracked_until", "outcomes", ["tracked_until"], unique=False)

    op.create_table(
        "model_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("feature_set_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("training_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mlflow_run_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("promoted", sa.Boolean(), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_model_runs"),
    )
    op.create_index("ix_model_runs_model_name", "model_runs", ["model_name"], unique=False)
    op.create_index("ix_model_runs_status", "model_runs", ["status"], unique=False)
    op.create_index("ix_model_runs_mlflow_run_id", "model_runs", ["mlflow_run_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_model_runs_mlflow_run_id", table_name="model_runs")
    op.drop_index("ix_model_runs_status", table_name="model_runs")
    op.drop_index("ix_model_runs_model_name", table_name="model_runs")
    op.drop_table("model_runs")

    op.drop_index("ix_outcomes_tracked_until", table_name="outcomes")
    op.drop_index("ix_outcomes_evaluation_status", table_name="outcomes")
    op.drop_index("ix_outcomes_signal_id", table_name="outcomes")
    op.drop_table("outcomes")

    op.drop_index("ix_trade_plans_known_at", table_name="trade_plans")
    op.drop_index("ix_trade_plans_plan_timestamp", table_name="trade_plans")
    op.drop_index("ix_trade_plans_signal_id", table_name="trade_plans")
    op.drop_table("trade_plans")

    op.drop_index("ix_signals_setup_state", table_name="signals")
    op.drop_index("ix_signals_bias_htf", table_name="signals")
    op.drop_index("ix_signals_grade", table_name="signals")
    op.drop_index("ix_signals_signal", table_name="signals")
    op.drop_index("ix_signals_known_at", table_name="signals")
    op.drop_index("ix_signals_symbol_signal_timestamp", table_name="signals")
    op.drop_table("signals")

    op.drop_index("ix_features_known_at", table_name="features")
    op.drop_index("ix_features_bar_timestamp", table_name="features")
    op.drop_index("ix_features_symbol_id", table_name="features")
    op.drop_table("features")

    op.drop_index("ix_bars_timeframe_bar_timestamp", table_name="bars")
    op.drop_index("ix_bars_symbol_timeframe_known_at", table_name="bars")
    op.drop_table("bars")

    op.drop_index("ix_universe_snapshot_memberships_symbol_id", table_name="universe_snapshot_memberships")
    op.drop_index("ix_universe_snapshot_memberships_snapshot_id", table_name="universe_snapshot_memberships")
    op.drop_table("universe_snapshot_memberships")

    op.drop_index("ix_universe_snapshots_snapshot_timestamp", table_name="universe_snapshots")
    op.drop_table("universe_snapshots")

    op.drop_table("symbols")

    evaluation_status.drop(bind, checkfirst=True)
    trail_mode.drop(bind, checkfirst=True)
    entry_type.drop(bind, checkfirst=True)
    htf_bias.drop(bind, checkfirst=True)
    signal_grade.drop(bind, checkfirst=True)
    signal_value.drop(bind, checkfirst=True)
    timeframe.drop(bind, checkfirst=True)
    universe_tier.drop(bind, checkfirst=True)
    universe_refresh_session.drop(bind, checkfirst=True)
    market_data_source.drop(bind, checkfirst=True)
    listed_exchange.drop(bind, checkfirst=True)
