from __future__ import annotations

from fixed_income.config.text_utils import security_text_blob

SPREAD_PROXY_BY_BUCKET = {
    "Investment Grade Credit": "BAMLC0A0CM",
    "High Yield": "BAMLH0A0HYM2",
}


def spread_proxy_for_bucket(bucket: str, security) -> str | None:
    text_blob = security_text_blob(security)
    if bucket == "Investment Grade Credit":
        return "BAMLC0A4CBBB" if "bbb" in text_blob else "BAMLC0A0CM"
    if bucket == "High Yield":
        return "BAMLH0A2HYB" if "single-b" in text_blob or "single b" in text_blob else "BAMLH0A0HYM2"
    return None
