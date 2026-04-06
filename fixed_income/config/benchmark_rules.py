from __future__ import annotations

from fixed_income.config.bucket_rules import duration_hint


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


def duration_band(rough_duration: float | None, security) -> str:
    if rough_duration is not None:
        if rough_duration < 3.0:
            return "short"
        if rough_duration >= 8.0:
            return "long"
        return "intermediate"

    hint = duration_hint(security)
    if any(token in hint for token in ("short", "ultra short", "1-3")):
        return "short"
    if any(token in hint for token in ("long", "20", "30")):
        return "long"
    return "intermediate"


def benchmark_for_bucket(bucket: str, rough_duration: float | None, security) -> str:
    if bucket == "Investment Grade Credit":
        return "IEF"
    if bucket == "High Yield":
        return "SHY"
    if bucket == "Muni":
        return "IEF"
    if bucket == "Mortgage / Securitized":
        return "VGIT" if duration_band(rough_duration, security) == "intermediate" else "IEF"
    if bucket in {"Short Duration / Cash-like", "Floating Rate"}:
        return "SHY"
    if bucket == "Preferred / Hybrid":
        return "IEF"

    band = duration_band(rough_duration, security)
    if band == "short":
        return "SHY"
    if band == "long":
        return "TLT"
    return "IEF"
