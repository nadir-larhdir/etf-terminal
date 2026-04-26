"""Shared constants that govern the analytics model's behaviour and versioning."""

# FRED series IDs representing the full US Treasury curve used as rate factors.
RATE_SERIES = (
    "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS3",
    "DGS5", "DGS7", "DGS10", "DGS20", "DGS30",
)

# Human-readable label summarising all rate factor tenors used in the model.
RATE_FACTOR_LABEL = "DGS3MO + DGS6MO + DGS1 + DGS2 + DGS3 + DGS5 + DGS7 + DGS10 + DGS20 + DGS30"

# Smoothing parameter for EWMA weighting; higher values decay faster toward recent observations.
EWMA_ALPHA = 0.65

# Minimum number of clean observations required before any regression is attempted.
MIN_OBSERVATIONS = 20

# Version tag embedded in every analytics snapshot for audit and comparison purposes.
ANALYTICS_MODEL_VERSION = "fi_analytics_v1"
