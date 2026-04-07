from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import text

from db.sql import qualified_table
from fixed_income.analytics.result_models import SecurityAnalyticsSnapshot


class AnalyticsSnapshotStore:
    """Persist and retrieve precomputed fixed-income analytics snapshots."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_snapshot(self, snapshot: SecurityAnalyticsSnapshot, *, as_of_date: str) -> None:
        payload = snapshot.to_record()
        payload["as_of_date"] = as_of_date
        payload["updated_at"] = datetime.utcnow().isoformat()
        statement = """
        INSERT INTO {snapshot_table} (
            symbol,
            as_of_date,
            asset_bucket,
            benchmark_used,
            spread_proxy_used,
            estimated_duration,
            rate_dv01_per_share,
            cs01_proxy_per_share,
            spread_beta_per_bp,
            equity_beta,
            rate_model_r2,
            spread_model_r2,
            confidence_level,
            model_type,
            rate_proxy_used,
            model_version,
            computed_from_start_date,
            computed_from_end_date,
            notes,
            reason,
            lookback_days_used,
            observations_used,
            updated_at
        ) VALUES (
            :symbol,
            :as_of_date,
            :asset_bucket,
            :benchmark_used,
            :spread_proxy_used,
            :estimated_duration,
            :rate_dv01_per_share,
            :cs01_proxy_per_share,
            :spread_beta_per_bp,
            :equity_beta,
            :rate_model_r2,
            :spread_model_r2,
            :confidence_level,
            :model_type,
            :rate_proxy_used,
            :model_version,
            :computed_from_start_date,
            :computed_from_end_date,
            :notes,
            :reason,
            :lookback_days_used,
            :observations_used,
            :updated_at
        )
        ON CONFLICT(symbol, as_of_date) DO UPDATE SET
            asset_bucket = excluded.asset_bucket,
            benchmark_used = excluded.benchmark_used,
            spread_proxy_used = excluded.spread_proxy_used,
            estimated_duration = excluded.estimated_duration,
            rate_dv01_per_share = excluded.rate_dv01_per_share,
            cs01_proxy_per_share = excluded.cs01_proxy_per_share,
            spread_beta_per_bp = excluded.spread_beta_per_bp,
            equity_beta = excluded.equity_beta,
            rate_model_r2 = excluded.rate_model_r2,
            spread_model_r2 = excluded.spread_model_r2,
            confidence_level = excluded.confidence_level,
            model_type = excluded.model_type,
            rate_proxy_used = excluded.rate_proxy_used,
            model_version = excluded.model_version,
            computed_from_start_date = excluded.computed_from_start_date,
            computed_from_end_date = excluded.computed_from_end_date,
            notes = excluded.notes,
            reason = excluded.reason,
            lookback_days_used = excluded.lookback_days_used,
            observations_used = excluded.observations_used,
            updated_at = excluded.updated_at
        """.format(snapshot_table=qualified_table(self.engine, "analytics_snapshots"))
        with self.engine.begin() as conn:
            conn.execute(text(statement), payload)

    def get_latest_snapshot(self, symbol: str) -> SecurityAnalyticsSnapshot | None:
        query = text(
            f"""
            SELECT *
            FROM {qualified_table(self.engine, 'analytics_snapshots')}
            WHERE symbol = :symbol
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"symbol": symbol})
        if df.empty:
            return None
        return SecurityAnalyticsSnapshot.from_record(df.iloc[0].to_dict())

    def get_latest_snapshots(self, symbols: list[str]) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()
        placeholders = ", ".join(f":symbol_{idx}" for idx in range(len(symbols)))
        query = text(
            f"""
            WITH ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY as_of_date DESC) AS rn
                FROM {qualified_table(self.engine, 'analytics_snapshots')}
                WHERE symbol IN ({placeholders})
            )
            SELECT *
            FROM ranked
            WHERE rn = 1
            ORDER BY symbol
            """
        )
        params = {f"symbol_{idx}": symbol for idx, symbol in enumerate(symbols)}
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params=params)
