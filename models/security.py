from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


def _empty_series() -> pd.Series:
    return pd.Series(dtype=float)


@dataclass
class Security:
    """Represent one ETF and expose convenience methods around its stored history."""

    ticker: str
    name: str | None = None
    asset_class: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    history: pd.DataFrame = field(default_factory=pd.DataFrame)

    RATE_SERIES = ("DGS2", "DGS5", "DGS10", "DGS30")
    RATE_FACTOR_LABEL = "DGS2 + DGS5 + DGS10 + DGS30"
    @property
    def has_history(self) -> bool:
        return not self.history.empty

    def set_history(self, history: pd.DataFrame) -> None:
        self.history = history.copy()

    def set_metadata(self, metadata: dict[str, Any] | None) -> None:
        self.metadata = metadata.copy() if metadata else {}

    def load_history(self, price_store) -> pd.DataFrame:
        self.history = price_store.get_ticker_price_history(self.ticker)
        return self.history

    def load_metadata(self, metadata_store) -> dict[str, Any]:
        loaded = metadata_store.get_ticker_metadata(self.ticker)
        self.metadata = loaded.copy() if loaded else {}
        return self.metadata

    def last_price(self) -> float | None:
        if self.history.empty or "close" not in self.history.columns:
            return None
        return float(self.history["close"].iloc[-1])

    def last_volume(self) -> float | None:
        if self.history.empty or "volume" not in self.history.columns:
            return None
        return float(self.history["volume"].iloc[-1])

    def close_series(self) -> pd.Series:
        if self.history.empty or "close" not in self.history.columns:
            return _empty_series()
        return self.history["close"].copy()

    def adj_close_series(self) -> pd.Series:
        if self.history.empty:
            return _empty_series()
        column = "adj_close" if "adj_close" in self.history.columns else "close"
        if column not in self.history.columns:
            return _empty_series()
        return self.history[column].copy()

    def volume_series(self) -> pd.Series:
        if self.history.empty or "volume" not in self.history.columns:
            return _empty_series()
        return self.history["volume"].copy()

    def returns(self) -> pd.Series:
        prices = self.adj_close_series()
        if prices.empty:
            return _empty_series()
        return prices.pct_change().dropna()

    def log_returns(self) -> pd.Series:
        prices = self.adj_close_series()
        if prices.empty:
            return _empty_series()
        logged = np.log(prices.replace(0, np.nan)).dropna()
        return logged.diff().dropna()

    def normalized_price(self, base: float = 100.0) -> pd.Series:
        close = self.close_series()
        if close.empty:
            return _empty_series()
        first_value = float(close.iloc[0])
        if first_value == 0:
            return pd.Series(dtype=float, index=close.index)
        return (close / first_value) * base

    def rolling_volume_mean(self, window: int = 30) -> pd.Series:
        volume = self.volume_series()
        if volume.empty:
            return _empty_series()
        return volume.rolling(window).mean()

    def history_between(self, start_date, end_date) -> pd.DataFrame:
        if self.history.empty:
            return self.history.copy()
        filtered = self.history.loc[
            (self.history.index.date >= start_date.date()) & (self.history.index.date <= end_date.date())
        ].copy()
        return filtered if not filtered.empty else self.history.tail(1).copy()

    def trading_snapshot(self, volume_window: int = 30) -> dict[str, float | None]:
        if self.history.empty:
            return {
                "latest_price": None,
                "current_volume": None,
                "average_volume": None,
                "volume_z": None,
                "range_position": None,
            }

        latest_price = self.last_price()
        current_volume = self.last_volume()
        volume = self.volume_series()
        average_volume = float(volume.tail(volume_window).mean()) if not volume.empty else None
        std_volume = float(volume.tail(volume_window).std(ddof=0)) if len(volume.tail(volume_window)) > 1 else None
        volume_z = None if std_volume in (None, 0.0) or current_volume is None or average_volume is None else (current_volume - average_volume) / std_volume

        high = float(self.history["high"].iloc[-1]) if "high" in self.history.columns else None
        low = float(self.history["low"].iloc[-1]) if "low" in self.history.columns else None
        range_position = 0.5
        if latest_price is not None and high is not None and low is not None and high != low:
            range_position = (latest_price - low) / (high - low)

        return {
            "latest_price": latest_price,
            "current_volume": current_volume,
            "average_volume": average_volume,
            "volume_z": volume_z,
            "range_position": range_position,
        }

    def rate_risk_proxy(self, macro_store, price_store, duration_selector) -> dict[str, Any]:
        """Estimate duration and DV01 from ETF log returns versus Treasury and credit factors."""

        returns = self.log_returns()
        latest_price = self.last_price()
        if returns.empty or latest_price is None:
            return self._empty_rate_risk_proxy("Insufficient ETF price history.")

        start_date = (returns.index.max() - pd.Timedelta(days=260)).date().isoformat()
        rates = macro_store.get_series_matrix(list(self.RATE_SERIES), start_date=start_date)
        if rates.empty:
            return self._empty_rate_risk_proxy("Treasury rate history is unavailable.")

        missing = [series_id for series_id in self.RATE_SERIES if series_id not in rates.columns]
        if missing:
            return self._empty_rate_risk_proxy(f"Missing Treasury series: {', '.join(missing)}.")

        rate_changes_bps = rates.loc[:, list(self.RATE_SERIES)].astype(float).diff().mul(100.0).dropna()
        aligned = returns.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
        if len(aligned) < 20:
            return self._empty_rate_risk_proxy("Not enough overlapping ETF and Treasury observations.")

        curve_60d = self._regress_curve_duration(aligned.tail(60), 60)
        curve_120d = self._regress_curve_duration(aligned.tail(120), 120)
        rough_duration = self._ewma_blend([curve_120d["estimated_duration"], curve_60d["estimated_duration"]])
        selection = duration_selector.select_for_security(self, rough_duration=rough_duration)
        bucket = str(selection["asset_bucket"])
        model_type = str(selection["duration_model_type"])
        benchmark_used = selection["treasury_benchmark_symbol"]

        headline_60d = curve_60d
        headline_120d = curve_120d
        benchmark_duration = None
        spread_beta_per_bp = None
        spread_model_r2 = None
        spread_proxy_used = self._spread_proxy_series_id(bucket)
        if model_type == "treasury_etf_benchmark_regression" and benchmark_used:
            benchmark_duration = self._benchmark_duration_proxy(str(benchmark_used), macro_store, price_store)
            benchmark_returns = self._benchmark_returns(str(benchmark_used), price_store, start_date)
            if benchmark_duration is not None and not benchmark_returns.empty:
                benchmark_frame = aligned.join(benchmark_returns.rename("benchmark_return"), how="inner")
                if bucket in {"Investment Grade Credit", "High Yield"} and spread_proxy_used:
                    spread_matrix = macro_store.get_series_matrix([spread_proxy_used], start_date=start_date)
                    if not spread_matrix.empty and spread_proxy_used in spread_matrix.columns:
                        spread_change = (
                            spread_matrix[spread_proxy_used]
                            .astype(float)
                            .diff()
                            .mul(100.0)
                            .dropna()
                            .rename("spread_change_bps")
                        )
                        benchmark_frame = benchmark_frame.join(spread_change, how="inner")
                        if len(benchmark_frame) >= 20:
                            headline_60d = self._regress_credit_benchmark_duration(
                                benchmark_frame.tail(60), 60, benchmark_duration
                            )
                            headline_120d = self._regress_credit_benchmark_duration(
                                benchmark_frame.tail(120), 120, benchmark_duration
                            )
                            spread_beta_per_bp = self._ewma_blend(
                                [headline_120d["credit_beta"], headline_60d["credit_beta"]]
                            )
                            spread_model_r2 = self._ewma_blend(
                                [headline_120d["regression_r2"], headline_60d["regression_r2"]]
                            )
                elif len(benchmark_frame) >= 20:
                    headline_60d = self._regress_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
                    headline_120d = self._regress_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)

        rate_duration_raw = self._ewma_blend([curve_120d["estimated_duration"], curve_60d["estimated_duration"]])
        estimated_duration = self._ewma_blend([headline_120d["estimated_duration"], headline_60d["estimated_duration"]])
        rate_model_r2 = self._ewma_blend([headline_120d["regression_r2"], headline_60d["regression_r2"]])
        dv01_per_share = None if estimated_duration is None else estimated_duration * latest_price * 0.0001
        reason = headline_120d["reason"] or headline_60d["reason"]
        observations_used = headline_120d["observations_used"] or headline_60d["observations_used"]

        residual_rate_duration = None
        if spread_proxy_used and spread_beta_per_bp is None:
            spread_matrix = macro_store.get_series_matrix([spread_proxy_used], start_date=start_date)
            if not spread_matrix.empty and spread_proxy_used in spread_matrix.columns:
                spread_change = spread_matrix[spread_proxy_used].astype(float).diff().mul(100.0).dropna().rename("spread_change_bps")
                spread_frame = aligned.join(spread_change, how="inner")
                if len(spread_frame) >= 20:
                    spread_columns = [*self.RATE_SERIES, "spread_change_bps"]
                    spread_model_60d = self._regress_duration(spread_frame.tail(60), 60, spread_columns)
                    spread_model_120d = self._regress_duration(spread_frame.tail(120), 120, spread_columns)
                    spread_beta_per_bp = self._ewma_blend(
                        [spread_model_120d["credit_beta"], spread_model_60d["credit_beta"]]
                    )
                    spread_model_r2 = self._ewma_blend(
                        [spread_model_120d["regression_r2"], spread_model_60d["regression_r2"]]
                    )
                    residual_rate_duration = self._ewma_blend(
                        [spread_model_120d["estimated_duration"], spread_model_60d["estimated_duration"]]
                    )
                    reason = reason or spread_model_120d["reason"] or spread_model_60d["reason"]
        spread_dv01_proxy_per_share = (
            None if spread_beta_per_bp is None else abs(spread_beta_per_bp) * latest_price
        )
        if bucket == "High Yield":
            hy_reason = " High-yield duration is model-based and more sensitive to benchmark and spread specification than Treasury or IG estimates."
            reason = (reason or "").strip() + hy_reason

        return {
            "bucket": bucket,
            "model_type_used": model_type,
            "benchmark_used": benchmark_used,
            "rate_proxy_used": selection["rate_proxy_description"],
            "estimated_duration": estimated_duration,
            "rate_duration_raw": rate_duration_raw,
            "benchmark_duration": benchmark_duration,
            "estimated_duration_60d": headline_60d["estimated_duration"],
            "estimated_duration_120d": headline_120d["estimated_duration"],
            "regression_r2": rate_model_r2,
            "rate_model_r2": rate_model_r2,
            "credit_model_r2": spread_model_r2,
            "lookback_days_used": 120 if headline_120d["estimated_duration"] is not None else headline_60d["lookback_days_used"],
            "observations_used": observations_used,
            "dv01_per_share": dv01_per_share,
            "ir01_per_share": dv01_per_share,
            "credit_beta": spread_beta_per_bp,
            "spread_beta_proxy": spread_beta_per_bp,
            "spread_beta_per_bp": spread_beta_per_bp,
            "spread_r2": spread_model_r2,
            "spread_model_r2": spread_model_r2,
            "spread_proxy_used": spread_proxy_used,
            "spread_dv01_proxy_per_share": spread_dv01_proxy_per_share,
            "residual_rate_duration": residual_rate_duration,
            "confidence_level": selection["confidence_level"],
            "notes": selection["notes"],
            "reason": (reason or "").strip() or None,
        }

    def _regress_curve_duration(self, frame: pd.DataFrame, lookback_days: int) -> dict[str, Any]:
        return self._regress_duration(frame, lookback_days, list(self.RATE_SERIES))

    def _regress_benchmark_duration(
        self,
        frame: pd.DataFrame,
        lookback_days: int,
        benchmark_duration: float,
    ) -> dict[str, Any]:
        if len(frame) < max(20, lookback_days // 3):
            return {
                "estimated_duration": None,
                "regression_r2": None,
                "lookback_days_used": len(frame),
                "observations_used": len(frame),
                "credit_beta": None,
                "reason": "Not enough observations for benchmark regression.",
            }

        filtered = self._filter_outliers(frame)
        if len(filtered) < max(20, lookback_days // 3):
            return {
                "estimated_duration": None,
                "regression_r2": None,
                "lookback_days_used": len(filtered),
                "observations_used": len(filtered),
                "credit_beta": None,
                "reason": "Not enough observations after outlier filtering.",
            }

        y = filtered["etf_return"].to_numpy(dtype=float)
        x = filtered["benchmark_return"].to_numpy(dtype=float)
        weights = self._ewma_weights(len(filtered), lookback_days)
        design = np.column_stack([np.ones(len(filtered)), x])
        sqrt_w = np.sqrt(weights)
        coeffs = np.linalg.lstsq(design * sqrt_w[:, None], y * sqrt_w, rcond=None)[0]
        fitted = coeffs[0] + coeffs[1] * x
        weighted_mean = float(np.average(y, weights=weights))
        total = float(np.sum(weights * (y - weighted_mean) ** 2))
        residual = float(np.sum(weights * (y - fitted) ** 2))
        r2 = None if total <= 0 else max(0.0, 1.0 - residual / total)
        return {
            "estimated_duration": float(coeffs[1] * benchmark_duration),
            "regression_r2": None if r2 is None else float(r2),
            "lookback_days_used": lookback_days,
            "observations_used": len(filtered),
            "credit_beta": None,
            "reason": None,
        }

    def _regress_credit_benchmark_duration(
        self,
        frame: pd.DataFrame,
        lookback_days: int,
        benchmark_duration: float,
    ) -> dict[str, Any]:
        if len(frame) < max(20, lookback_days // 3):
            return {
                "estimated_duration": None,
                "regression_r2": None,
                "lookback_days_used": len(frame),
                "observations_used": len(frame),
                "credit_beta": None,
                "reason": "Not enough observations for benchmark and spread regression.",
            }

        filtered = self._filter_outliers(frame)
        if len(filtered) < max(20, lookback_days // 3):
            return {
                "estimated_duration": None,
                "regression_r2": None,
                "lookback_days_used": len(filtered),
                "observations_used": len(filtered),
                "credit_beta": None,
                "reason": "Not enough observations after outlier filtering.",
            }

        y = filtered["etf_return"].to_numpy(dtype=float)
        x = filtered.loc[:, ["benchmark_return", "spread_change_bps"]].to_numpy(dtype=float)
        weights = self._ewma_weights(len(filtered), lookback_days)
        design = np.column_stack([np.ones(len(filtered)), x])
        sqrt_w = np.sqrt(weights)
        coeffs = np.linalg.lstsq(design * sqrt_w[:, None], y * sqrt_w, rcond=None)[0]
        fitted = design @ coeffs
        weighted_mean = float(np.average(y, weights=weights))
        total = float(np.sum(weights * (y - weighted_mean) ** 2))
        residual = float(np.sum(weights * (y - fitted) ** 2))
        r2 = None if total <= 0 else max(0.0, 1.0 - residual / total)
        return {
            "estimated_duration": float(coeffs[1] * benchmark_duration),
            "regression_r2": None if r2 is None else float(r2),
            "lookback_days_used": lookback_days,
            "observations_used": len(filtered),
            "credit_beta": float(coeffs[2]),
            "reason": None,
        }

    def _benchmark_duration_proxy(self, benchmark_ticker: str, macro_store, price_store) -> float | None:
        benchmark_history = price_store.get_ticker_price_history(benchmark_ticker)
        if benchmark_history.empty:
            return None
        benchmark = Security(benchmark_ticker, history=benchmark_history)
        returns = benchmark.log_returns()
        if returns.empty:
            return None
        start_date = (returns.index.max() - pd.Timedelta(days=260)).date().isoformat()
        rates = macro_store.get_series_matrix(list(self.RATE_SERIES), start_date=start_date)
        if rates.empty or any(series_id not in rates.columns for series_id in self.RATE_SERIES):
            return None
        rate_changes_bps = rates.loc[:, list(self.RATE_SERIES)].astype(float).diff().mul(100.0).dropna()
        aligned = returns.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
        if len(aligned) < 20:
            return None
        model_60d = benchmark._regress_curve_duration(aligned.tail(60), 60)
        model_120d = benchmark._regress_curve_duration(aligned.tail(120), 120)
        return self._ewma_blend([model_120d["estimated_duration"], model_60d["estimated_duration"]])

    def _benchmark_returns(self, benchmark_ticker: str, price_store, start_date: str) -> pd.Series:
        benchmark_history = price_store.get_ticker_price_history(benchmark_ticker, start_date=start_date)
        if benchmark_history.empty:
            return _empty_series()
        column = "adj_close" if "adj_close" in benchmark_history.columns else "close"
        prices = benchmark_history[column].replace(0, np.nan).dropna()
        return np.log(prices).diff().dropna()

    def _regress_duration(
        self,
        frame: pd.DataFrame,
        lookback_days: int,
        factor_columns: list[str],
        orthogonalize_credit: bool = False,
    ) -> dict[str, Any]:
        if len(frame) < max(20, lookback_days // 3):
            return {
                "estimated_duration": None,
                "regression_r2": None,
                "lookback_days_used": len(frame),
                "observations_used": len(frame),
                "credit_beta": None,
                "reason": "Not enough observations for regression.",
            }

        filtered = self._filter_outliers(frame)
        if len(filtered) < max(20, lookback_days // 3):
            return {
                "estimated_duration": None,
                "regression_r2": None,
                "lookback_days_used": len(filtered),
                "observations_used": len(filtered),
                "credit_beta": None,
                "reason": "Not enough observations after outlier filtering.",
            }

        filtered = filtered.copy()
        if orthogonalize_credit and "credit_proxy_return" in factor_columns:
            filtered.loc[:, "credit_proxy_return"] = self._orthogonalize_credit_factor(filtered)

        y = filtered["etf_return"].to_numpy(dtype=float)
        x = filtered.loc[:, factor_columns].to_numpy(dtype=float)
        weights = self._ewma_weights(len(filtered), lookback_days)
        design = np.column_stack([np.ones(len(filtered)), x])
        sqrt_w = np.sqrt(weights)
        coeffs = np.linalg.lstsq(design * sqrt_w[:, None], y * sqrt_w, rcond=None)[0]
        intercept = coeffs[0]
        beta_map = dict(zip(factor_columns, coeffs[1:], strict=False))
        fitted = intercept + x @ coeffs[1:]
        weighted_mean = float(np.average(y, weights=weights))
        total = float(np.sum(weights * (y - weighted_mean) ** 2))
        residual = float(np.sum(weights * (y - fitted) ** 2))
        r2 = None if total <= 0 else max(0.0, 1.0 - residual / total)
        # Betas are estimated against yield changes in basis points, so rescale back to
        # a duration-like number using the standard 10,000 bps = 100% rate convention.
        rate_beta_sum = sum(float(beta_map.get(series_id, 0.0)) for series_id in self.RATE_SERIES)
        estimated_duration = float(-(rate_beta_sum * 10000.0))
        return {
            "estimated_duration": estimated_duration,
            "regression_r2": None if r2 is None else float(r2),
            "lookback_days_used": lookback_days,
            "observations_used": len(filtered),
            "credit_beta": self._factor_beta(beta_map),
            "reason": None,
        }

    def _empty_rate_risk_proxy(self, reason: str, rate_proxy: str | None = None) -> dict[str, Any]:
        return {
            "bucket": "Unknown",
            "model_type_used": None,
            "benchmark_used": None,
            "rate_proxy_used": rate_proxy or self.RATE_FACTOR_LABEL,
            "estimated_duration": None,
            "rate_duration_raw": None,
            "benchmark_duration": None,
            "estimated_duration_60d": None,
            "estimated_duration_120d": None,
            "regression_r2": None,
            "rate_model_r2": None,
            "credit_model_r2": None,
            "lookback_days_used": None,
            "observations_used": None,
            "dv01_per_share": None,
            "ir01_per_share": None,
            "credit_beta": None,
            "spread_beta_proxy": None,
            "spread_beta_per_bp": None,
            "spread_r2": None,
            "spread_model_r2": None,
            "spread_proxy_used": None,
            "spread_dv01_proxy_per_share": None,
            "residual_rate_duration": None,
            "confidence_level": "low",
            "notes": reason,
            "reason": reason,
        }

    def _ewma_blend(self, values: list[float | None], alpha: float = 0.65) -> float | None:
        valid = [value for value in values if value is not None and not pd.isna(value)]
        if not valid:
            return None
        return float(pd.Series(valid, dtype=float).ewm(alpha=alpha, adjust=False).mean().iloc[-1])

    def _ewma_weights(self, length: int, lookback_days: int) -> np.ndarray:
        half_life = max(10.0, lookback_days / 3.0)
        ages = np.arange(length - 1, -1, -1, dtype=float)
        return np.power(0.5, ages / half_life)

    def _filter_outliers(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        lower = frame["etf_return"].quantile(0.01)
        upper = frame["etf_return"].quantile(0.99)
        return frame.loc[frame["etf_return"].between(lower, upper)].copy()

    def _orthogonalize_credit_factor(self, frame: pd.DataFrame) -> np.ndarray:
        """Strip Treasury-curve co-movement from the credit factor before estimating credit beta."""

        y = frame["credit_proxy_return"].to_numpy(dtype=float)
        x = frame.loc[:, list(self.RATE_SERIES)].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(frame)), x])
        coeffs = np.linalg.lstsq(design, y, rcond=None)[0]
        return y - (design @ coeffs)

    def _spread_proxy_series_id(self, bucket: str) -> str | None:
        text_blob = " ".join(
            str(value or "")
            for value in (
                self.ticker,
                self.name,
                self.asset_class,
                self.metadata.get("category"),
                self.metadata.get("long_name"),
                self.metadata.get("description"),
            )
        ).lower()
        if bucket == "Investment Grade Credit":
            return "BAMLC0A4CBBB" if "bbb" in text_blob else "BAMLC0A0CM"
        if bucket == "High Yield":
            return "BAMLH0A2HYB" if "single-b" in text_blob or "single b" in text_blob else "BAMLH0A0HYM2"
        return None

    def _factor_beta(self, beta_map: dict[str, float]) -> float | None:
        for factor_name in ("spread_change_bps", "credit_proxy_return"):
            if factor_name in beta_map:
                return float(beta_map[factor_name])
        return None
