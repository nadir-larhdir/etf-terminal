"""Read/write precomputed fixed-income analytics snapshots."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import text

from db.sql import qualified_table
from fixed_income.analytics.result_models import SecurityAnalyticsSnapshot
from stores.query_utils import sql_in_clause_params


class AnalyticsSnapshotStore:
    """Persist and retrieve per-symbol analytics snapshots keyed by (symbol, as_of_date)."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_snapshot(self, snapshot: SecurityAnalyticsSnapshot, *, as_of_date: str) -> None:
        """Insert or update a single analytics snapshot for the given date."""
        payload = snapshot.to_record()
        payload["as_of_date"] = as_of_date
        payload["updated_at"] = datetime.utcnow().isoformat()
        statement = f"""
        INSERT INTO {qualified_table(self.engine, 'analytics_snapshots')} (
            symbol, as_of_date, asset_bucket, benchmark_used, spread_proxy_used,
            estimated_duration, rate_dv01_per_share, benchmark_beta, cs01_proxy_per_share,
            spread_beta_per_bp, equity_beta, rate_model_r2, spread_model_r2,
            confidence_level, model_type, rate_proxy_used, model_version,
            computed_from_start_date, computed_from_end_date, notes, reason,
            lookback_days_used, observations_used, updated_at
        ) VALUES (
            :symbol, :as_of_date, :asset_bucket, :benchmark_used, :spread_proxy_used,
            :estimated_duration, :rate_dv01_per_share, :benchmark_beta, :cs01_proxy_per_share,
            :spread_beta_per_bp, :equity_beta, :rate_model_r2, :spread_model_r2,
            :confidence_level, :model_type, :rate_proxy_used, :model_version,
            :computed_from_start_date, :computed_from_end_date, :notes, :reason,
            :lookback_days_used, :observations_used, :updated_at
        )
        ON CONFLICT(symbol, as_of_date) DO UPDATE SET
            asset_bucket = excluded.asset_bucket, benchmark_used = excluded.benchmark_used,
            spread_proxy_used = excluded.spread_proxy_used, estimated_duration = excluded.estimated_duration,
            rate_dv01_per_share = excluded.rate_dv01_per_share, benchmark_beta = excluded.benchmark_beta,
            cs01_proxy_per_share = excluded.cs01_proxy_per_share, spread_beta_per_bp = excluded.spread_beta_per_bp,
            equity_beta = excluded.equity_beta, rate_model_r2 = excluded.rate_model_r2,
            spread_model_r2 = excluded.spread_model_r2, confidence_level = excluded.confidence_level,
            model_type = excluded.model_type, rate_proxy_used = excluded.rate_proxy_used,
            model_version = excluded.model_version,
            computed_from_start_date = excluded.computed_from_start_date,
            computed_from_end_date = excluded.computed_from_end_date,
            notes = excluded.notes, reason = excluded.reason,
            lookback_days_used = excluded.lookback_days_used, observations_used = excluded.observations_used,
            updated_at = excluded.updated_at
        """
        with self.engine.begin() as conn:
            conn.execute(text(statement), payload)

    def get_latest_snapshot(self, symbol: str) -> SecurityAnalyticsSnapshot | None:
        """Return the most recent snapshot for a symbol, or None if not found."""
        query = text(f"""
            SELECT * FROM {qualified_table(self.engine, 'analytics_snapshots')}
            WHERE symbol = :symbol ORDER BY as_of_date DESC LIMIT 1
        """)
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"symbol": symbol})
        if df.empty:
            return None
        return SecurityAnalyticsSnapshot.from_record(df.iloc[0].to_dict())

    def get_latest_snapshots(self, symbols: list[str]) -> pd.DataFrame:
        """Return a DataFrame of the most recent snapshot row for each requested symbol."""
        if not symbols:
            return pd.DataFrame()
        placeholders, params = sql_in_clause_params("symbol", symbols)
        query = text(f"""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY as_of_date DESC) AS rn
                FROM {qualified_table(self.engine, 'analytics_snapshots')}
                WHERE symbol IN ({placeholders})
            )
            SELECT * FROM ranked WHERE rn = 1 ORDER BY symbol
        """)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params=params)
