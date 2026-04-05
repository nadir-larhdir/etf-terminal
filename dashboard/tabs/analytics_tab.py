import streamlit as st

from dashboard.components.info_panel import InfoPanel
from dashboard.perf import timed_block
from models.security import Security


class AnalyticsTab:
    """Display single-security risk, fit, and liquidity diagnostics."""

    DURATION_ESTIMATES = {
        "Short Duration": 2.0,
        "7-10Y": 8.5,
        "20Y+": 17.0,
        "Intermediate Duration": 5.5,
        "Intermediate / Long Duration": 8.0,
        "Long Duration": 12.0,
        "Broad Market": 6.0,
        "Securitized": 4.0,
        "Floating Rate": 0.3,
        "Inflation-Linked": 7.0,
    }

    CREDIT_BETA_PROXIES = {
        "UST Short": 0.00,
        "UST Belly": 0.00,
        "UST Long": 0.00,
        "UST Broad": 0.00,
        "IG Credit": 0.55,
        "HY Credit": 1.00,
        "EM Debt": 0.80,
        "Core Bond": 0.35,
        "Floating Rate": 0.20,
        "Inflation-Linked": 0.05,
        "MBS": 0.30,
        "Municipal": 0.25,
    }

    BENCHMARK_PROXIES = {
        "UST Short": ["VGSH", "SHY"],
        "UST Belly": ["IEF", "IEI"],
        "UST Long": ["TLT", "EDV"],
        "UST Broad": ["GOVT"],
        "IG Credit": ["LQD", "VCIT"],
        "HY Credit": ["HYG", "JNK"],
        "EM Debt": ["EMB", "VWOB"],
        "Core Bond": ["AGG", "BND"],
        "Floating Rate": ["FLOT", "FLRN"],
        "Inflation-Linked": ["TIP", "STIP"],
        "MBS": ["MBB", "VMBS"],
        "Municipal": ["MUB", "VTEB"],
    }

    def __init__(self, price_store) -> None:
        self.price_store = price_store
        self.info_panel = InfoPanel()

    def render(self, security: Security) -> None:
        st.subheader("Analytics")
        with timed_block("analytics.prepare_inputs"):
            hist = security.history
            metadata = security.metadata or {}
            asset_bucket = security.asset_class or metadata.get("category") or "N/A"

            px_last = security.last_price() or 0.0
            close_series = security.close_series()
            prev_close = float(close_series.iloc[-2]) if len(close_series) > 1 else px_last

            volume = security.volume_series()
            current_vol = security.last_volume() or 0.0
            vol_mean_30d = float(volume.tail(30).mean()) if not volume.empty else 0.0
            vol_std_30d = float(volume.tail(30).std(ddof=0)) if len(volume.tail(30)) > 1 else 0.0
            vol_z = (current_vol - vol_mean_30d) / vol_std_30d if vol_std_30d != 0 else 0.0

            high = float(hist["high"].iloc[-1])
            low = float(hist["low"].iloc[-1])
            range_position = ((px_last - low) / (high - low)) if high != low else 0.5

            estimated_duration = self._estimated_duration(metadata)
            dv01_per_share = self._dv01_per_share(estimated_duration, px_last)
            credit_beta_proxy = self._credit_beta_proxy(asset_bucket)
            model_fit, model_label = self._model_fit(security, asset_bucket)
            liquidity_regime = self._liquidity_regime(vol_z)
            asset_regime = self._asset_regime_note(asset_bucket, metadata)

        a1, a2, a3, a4, a5 = st.columns(5)
        with a1:
            st.metric("ESTIMATED DURATION", f"{estimated_duration:.1f}y" if estimated_duration is not None else "N/A")
        with a2:
            st.metric("DV01 PER SHARE", f"${dv01_per_share:.4f}" if dv01_per_share is not None else "N/A")
        with a3:
            st.metric("CREDIT BETA PROXY", f"{credit_beta_proxy:.2f}")
        with a4:
            st.metric("MODEL FIT (R²)", f"{model_fit:.2f}" if model_fit is not None else "N/A", model_label)
        with a5:
            st.metric("ASSET BUCKET", asset_bucket)

        tone = "orderly"
        if liquidity_regime == "HIGH ACTIVITY":
            tone = "elevated"
        elif liquidity_regime == "QUIET":
            tone = "subdued"

        self.info_panel.render_note(
            title="Current Read",
            body=(
                f"{security.ticker} screens as {asset_regime}. Estimated duration is "
                f"{estimated_duration:.1f} years and DV01 is about ${dv01_per_share:.4f} per share. "
                f"Trading participation is {tone}, with volume at "
                f"{((current_vol / vol_mean_30d) if vol_mean_30d else 0.0):.2f}x its 30-day average and the latest close at {range_position:.0%} of today’s range."
            ),
            accent_color="#FF9F1A",
            margin_top="0.30rem",
            margin_bottom="0.30rem",
        )

        self.info_panel.render(
            title="Asset Bucket / Regime Note",
            headline=asset_bucket,
            body=asset_regime,
            accent_color="#5DA9E9",
            margin_top="0.35rem",
            margin_bottom="0.20rem",
        )

        self.info_panel.render(
            title="Trading Activity",
            headline=liquidity_regime,
            body="Based on current volume versus the trailing 30-day average and its standardized z-score.",
            accent_color="#00ADB5",
            margin_top="0.35rem",
            margin_bottom="0.00rem",
        )

    def _estimated_duration(self, metadata: dict) -> float | None:
        duration_bucket = str(metadata.get("duration_bucket") or "")
        return self.DURATION_ESTIMATES.get(duration_bucket)

    def _dv01_per_share(self, estimated_duration: float | None, price: float) -> float | None:
        if estimated_duration is None or price <= 0:
            return None
        return estimated_duration * price * 0.0001

    def _credit_beta_proxy(self, asset_bucket: str) -> float:
        return self.CREDIT_BETA_PROXIES.get(asset_bucket, 0.25)

    def _model_fit(self, security: Security, asset_bucket: str) -> tuple[float | None, str]:
        benchmark_ticker = self._benchmark_proxy_ticker(asset_bucket, security.ticker)
        if not benchmark_ticker:
            return None, "No proxy"

        security_history = security.history
        start_date = None
        if not security_history.empty:
            start_date = security_history.index.max() - pd.Timedelta(days=120)
        benchmark_hist = self.price_store.get_ticker_price_history(benchmark_ticker, start_date=start_date)
        if benchmark_hist.empty or "close" not in benchmark_hist.columns:
            return None, benchmark_ticker

        security_returns = security.returns().rename("security")
        benchmark_returns = benchmark_hist["close"].pct_change().dropna().rename("benchmark")
        aligned = security_returns.to_frame().join(benchmark_returns, how="inner").tail(60)
        if len(aligned) < 20:
            return None, benchmark_ticker

        correlation = aligned["security"].corr(aligned["benchmark"])
        if correlation is None:
            return None, benchmark_ticker
        return float(correlation ** 2), benchmark_ticker

    def _benchmark_proxy_ticker(self, asset_bucket: str, selected_ticker: str) -> str | None:
        candidates = self.BENCHMARK_PROXIES.get(asset_bucket, [])
        for ticker in candidates:
            if ticker != selected_ticker:
                return ticker
        return None

    def _asset_regime_note(self, asset_bucket: str, metadata: dict) -> str:
        duration_bucket = str(metadata.get("duration_bucket") or "N/A")
        benchmark = str(metadata.get("benchmark_index") or "N/A")
        return (
            f"{asset_bucket} exposure with a {duration_bucket.lower()} profile. "
            f"Benchmark context: {benchmark}."
        )

    def _liquidity_regime(self, vol_z: float) -> str:
        if vol_z > 2:
            return "HIGH ACTIVITY"
        if vol_z < -1:
            return "QUIET"
        return "NORMAL"
