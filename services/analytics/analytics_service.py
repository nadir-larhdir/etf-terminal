import pandas as pd


class AnalyticsService:
    """Compute reusable analytics derived from stored ETF price history."""

    @staticmethod
    def classify_liquidity(volume_vs_avg: float) -> str:
        if pd.isna(volume_vs_avg):
            return "Unknown"
        if volume_vs_avg > 1.5:
            return "Heavy / Eventful"
        if volume_vs_avg < 0.7:
            return "Quiet"
        return "Normal"

    @staticmethod
    def classify_rv(premium_discount: float) -> str:
        if premium_discount > 0.5:
            return "Rich"
        if premium_discount < -0.5:
            return "Cheap"
        return "Fair"

    @staticmethod
    def format_volume_label(value: float) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.0f}MM"
        if value >= 1_000:
            return f"{value / 1_000:.0f}M"
        return f"{value:.0f}"

    @staticmethod
    def filter_history_by_rows(hist: pd.DataFrame, rows: int) -> pd.DataFrame:
        return hist.tail(min(rows, len(hist))).copy() if not hist.empty else hist

    @staticmethod
    def filter_history_by_dates(hist: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
        if hist.empty:
            return hist
        filtered = hist.loc[(hist.index.date >= start_date) & (hist.index.date <= end_date)].copy()
        return filtered if not filtered.empty else hist.tail(1).copy()

    @staticmethod
    def compute_stats(filtered_hist: pd.DataFrame) -> dict:
        close_series = filtered_hist["close"]
        mean_price = float(close_series.mean())
        std_price = float(close_series.std(ddof=0)) if len(close_series) > 1 else 0.0
        return {
            "mean_price": mean_price,
            "std_price": std_price,
            "upper_band": mean_price + std_price,
            "lower_band": mean_price - std_price,
        }
