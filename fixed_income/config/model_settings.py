"""Shared constants that govern the analytics model's behaviour and versioning."""

# Smoothing parameter for EWMA weighting; higher values decay faster toward recent observations.
EWMA_ALPHA = 0.65

# Minimum number of clean observations required before any regression is attempted.
MIN_OBSERVATIONS = 20

# Version tag embedded in every analytics snapshot for audit and comparison purposes.
ANALYTICS_MODEL_VERSION = "fi_analytics_v1"
