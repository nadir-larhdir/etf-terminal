from __future__ import annotations


MODEL_LABELS = {
    "treasury_curve_regression": "Treasury Curve",
    "treasury_etf_benchmark_regression": "Treasury ETF Benchmark",
    "low_duration_assumption_with_validation": "Low-Duration Validation",
}

OAS_PROXY_LABELS = {
    "BAMLC0A0CM": "BoFA IG OAS",
    "BAMLC0A4CBBB": "BoFA BBB OAS",
    "BAMLH0A0HYM2": "BoFA HY OAS",
    "BAMLH0A2HYB": "BoFA Single-B OAS",
}


def format_model_label(model_type: str | None) -> str:
    return MODEL_LABELS.get(str(model_type), "N/A")


def format_oas_proxy_label(series_id: str | None) -> str:
    return OAS_PROXY_LABELS.get(str(series_id), series_id or "N/A")
