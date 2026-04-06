from __future__ import annotations

from services.analytics.result_models import DurationModelSelection


class DurationModelSelector:
    """Choose a duration model and Treasury ETF benchmark from simple ETF rules."""

    BENCHMARK_POOL = ("SHY", "IEF", "VGIT", "TLT")

    FALLBACK_OVERRIDES = {
        "SGOV": {
            "asset_bucket": "Short Duration / Cash-like",
            "duration_model_type": "treasury_etf_benchmark_regression",
            "treasury_benchmark_symbol": "SHY",
            "rate_proxy_description": "Short Treasury ETF benchmark (SHY-like).",
            "confidence_level": "high",
            "notes": "Explicit fallback for very short Treasury cash proxies.",
            "used_fallback": True,
        },
        "BIL": {
            "asset_bucket": "Short Duration / Cash-like",
            "duration_model_type": "treasury_etf_benchmark_regression",
            "treasury_benchmark_symbol": "SHY",
            "rate_proxy_description": "Short Treasury ETF benchmark (SHY-like).",
            "confidence_level": "high",
            "notes": "Explicit fallback for Treasury bill ETFs.",
            "used_fallback": True,
        },
        "TIP": {
            "asset_bucket": "Inflation-Linked",
            "duration_model_type": "treasury_curve_regression",
            "treasury_benchmark_symbol": None,
            "rate_proxy_description": "Treasury curve regression using DGS2, DGS5, DGS10, and DGS30.",
            "confidence_level": "high",
            "notes": "Explicit fallback keeps TIPS on the Treasury curve model.",
            "used_fallback": True,
        },
    }

    def select_for_security(self, security, rough_duration: float | None = None) -> DurationModelSelection:
        if security.ticker in self.FALLBACK_OVERRIDES:
            override = self.FALLBACK_OVERRIDES[security.ticker].copy()
            override["spread_proxy_series_id"] = self._spread_proxy_series_id(override["asset_bucket"], security)
            return DurationModelSelection(**override)

        bucket = self.classify_bucket(security)
        benchmark = None
        model_type = "treasury_curve_regression"
        notes = ""
        confidence = "medium"
        used_fallback = False

        if bucket in {"Treasury", "Inflation-Linked"}:
            model_type = "treasury_curve_regression"
            notes = "Rates estimated directly from Treasury curve factors."
            confidence = "high"
        elif bucket == "Floating Rate":
            model_type = "low_duration_assumption_with_validation"
            benchmark = "SHY"
            notes = "Floating-rate funds are validated against a short-duration benchmark."
            confidence = "medium"
        else:
            model_type = "treasury_etf_benchmark_regression"
            benchmark = self._select_benchmark(bucket, rough_duration, security)
            confidence = "high" if bucket != "Unknown" else "low"
            if bucket == "Unknown":
                used_fallback = True
                notes = "Unknown bucket fell back to a rule-based Treasury ETF benchmark."
            else:
                notes = f"{bucket} routed to Treasury ETF benchmark regression."

        description = (
            "Treasury curve regression using DGS2, DGS5, DGS10, and DGS30."
            if benchmark is None
            else f"Treasury ETF benchmark regression using {benchmark}."
        )
        return DurationModelSelection(
            asset_bucket=bucket,
            duration_model_type=model_type,
            treasury_benchmark_symbol=benchmark,
            spread_proxy_series_id=self._spread_proxy_series_id(bucket, security),
            rate_proxy_description=description,
            confidence_level=confidence,
            notes=notes,
            used_fallback=used_fallback,
        )

    def classify_bucket(self, security) -> str:
        text_blob = " ".join(
            str(value or "")
            for value in (
                security.ticker,
                security.name,
                security.asset_class,
                security.metadata.get("category"),
                security.metadata.get("long_name"),
                security.metadata.get("description"),
                security.metadata.get("duration_bucket"),
            )
        ).lower()

        if "tips" in text_blob or "inflation" in text_blob or security.asset_class == "Inflation-Linked":
            return "Inflation-Linked"
        if any(token in text_blob for token in ("floating rate", "bank loan", "loan participation")) or security.asset_class == "Floating Rate":
            return "Floating Rate"
        if any(token in text_blob for token in ("mortgage", "mbs", "securitized")) or security.asset_class == "MBS":
            return "Mortgage / Securitized"
        if any(token in text_blob for token in ("preferred", "hybrid")):
            return "Preferred / Hybrid"
        if any(token in text_blob for token in ("municipal", "muni")) or security.asset_class == "Municipal":
            return "Muni"
        if any(token in text_blob for token in ("high yield", "junk")) or security.asset_class == "HY Credit":
            return "High Yield"
        if any(token in text_blob for token in ("investment grade", "corporate bond", "credit")) or security.asset_class == "IG Credit":
            return "Investment Grade Credit"
        if any(token in text_blob for token in ("cash", "ultra short", "1-3 month", "1-3 year", "short treasury")) or security.asset_class == "UST Short":
            return "Short Duration / Cash-like"
        if "treasury" in text_blob or str(security.asset_class or "").startswith("UST "):
            return "Treasury"
        return "Unknown"

    def _select_benchmark(self, bucket: str, rough_duration: float | None, security) -> str:
        if bucket == "Investment Grade Credit":
            return "IEF"
        if bucket == "High Yield":
            return "SHY"
        if bucket == "Muni":
            return "IEF"
        if bucket == "Mortgage / Securitized":
            return "VGIT" if self._duration_band(rough_duration, security) == "intermediate" else "IEF"
        if bucket in {"Short Duration / Cash-like", "Floating Rate"}:
            return "SHY"
        if bucket == "Preferred / Hybrid":
            return "IEF"

        band = self._duration_band(rough_duration, security)
        if band == "short":
            return "SHY"
        if band == "long":
            return "TLT"
        return "IEF"

    def _duration_band(self, rough_duration: float | None, security) -> str:
        if rough_duration is not None:
            if rough_duration < 3.0:
                return "short"
            if rough_duration >= 8.0:
                return "long"
            return "intermediate"

        hint = self._duration_hint(security)
        if any(token in hint for token in ("short", "ultra short", "1-3")):
            return "short"
        if any(token in hint for token in ("long", "20", "30")):
            return "long"
        return "intermediate"

    def _duration_hint(self, security) -> str:
        return " ".join(
            str(value or "")
            for value in (
                security.metadata.get("duration_bucket"),
                security.name,
                security.metadata.get("long_name"),
                security.metadata.get("description"),
            )
        ).lower()

    def _spread_proxy_series_id(self, bucket: str, security) -> str | None:
        text_blob = " ".join(
            str(value or "")
            for value in (
                security.ticker,
                security.name,
                security.asset_class,
                security.metadata.get("category"),
                security.metadata.get("long_name"),
                security.metadata.get("description"),
            )
        ).lower()
        if bucket == "Investment Grade Credit":
            return "BAMLC0A4CBBB" if "bbb" in text_blob else "BAMLC0A0CM"
        if bucket == "High Yield":
            return "BAMLH0A2HYB" if "single-b" in text_blob or "single b" in text_blob else "BAMLH0A0HYM2"
        return None
