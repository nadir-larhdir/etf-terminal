"""Canonical registry for supported FRED macro series."""

MACRO_SERIES_REGISTRY = {
    "DGS2": {
        "name": "US Treasury 2-Year Yield",
        "category": "Rates",
        "sub_category": "Treasury Yields",
        "frequency": "Daily",
        "units": "Percent",
    },
    "DGS10": {
        "name": "US Treasury 10-Year Yield",
        "category": "Rates",
        "sub_category": "Treasury Yields",
        "frequency": "Daily",
        "units": "Percent",
    },
    "DGS30": {
        "name": "US Treasury 30-Year Yield",
        "category": "Rates",
        "sub_category": "Treasury Yields",
        "frequency": "Daily",
        "units": "Percent",
    },
    "CPIAUCSL": {
        "name": "Consumer Price Index",
        "category": "Inflation",
        "sub_category": "Headline CPI",
        "frequency": "Monthly",
        "units": "Index 1982-1984=100",
    },
    "T5YIE": {
        "name": "5-Year Breakeven Inflation",
        "category": "Inflation",
        "sub_category": "Market Inflation Expectations",
        "frequency": "Daily",
        "units": "Percent",
    },
    "FEDFUNDS": {
        "name": "Effective Federal Funds Rate",
        "category": "Policy",
        "sub_category": "Fed Policy Rate",
        "frequency": "Monthly",
        "units": "Percent",
    },
    "UNRATE": {
        "name": "US Unemployment Rate",
        "category": "Labor",
        "sub_category": "Employment",
        "frequency": "Monthly",
        "units": "Percent",
    },
}
