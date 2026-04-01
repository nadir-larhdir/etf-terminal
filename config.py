from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "market_data.db"

DEFAULT_TICKERS = {
    # Treasuries / Rates
    "SHY": {
        "name": "iShares 1-3 Year Treasury Bond ETF",
        "asset_class": "UST Short",
    },
    "VGSH": {
        "name": "Vanguard Short-Term Treasury ETF",
        "asset_class": "UST Short",
    },
    "IEI": {
        "name": "iShares 3-7 Year Treasury Bond ETF",
        "asset_class": "UST Belly",
    },
    "IEF": {
        "name": "iShares 7-10 Year Treasury Bond ETF",
        "asset_class": "UST Belly",
    },
    "GOVT": {
        "name": "iShares U.S. Treasury Bond ETF",
        "asset_class": "UST Broad",
    },
    "TLT": {
        "name": "iShares 20+ Year Treasury Bond ETF",
        "asset_class": "UST Long",
    },
    "EDV": {
        "name": "Vanguard Extended Duration Treasury ETF",
        "asset_class": "UST Long",
    },
    "TIP": {
        "name": "iShares TIPS Bond ETF",
        "asset_class": "Inflation",
    },
    "STIP": {
        "name": "iShares 0-5 Year TIPS Bond ETF",
        "asset_class": "Inflation",
    },

    # Core / Aggregate Bonds
    "AGG": {
        "name": "iShares Core U.S. Aggregate Bond ETF",
        "asset_class": "Core Bond",
    },
    "BND": {
        "name": "Vanguard Total Bond Market ETF",
        "asset_class": "Core Bond",
    },
    "IUSB": {
        "name": "iShares Core Total USD Bond Market ETF",
        "asset_class": "Core Bond",
    },

    # Investment Grade Credit
    "LQD": {
        "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "asset_class": "IG Credit",
    },
    "VCIT": {
        "name": "Vanguard Intermediate-Term Corporate Bond ETF",
        "asset_class": "IG Credit",
    },
    "IGSB": {
        "name": "iShares 1-5 Year Investment Grade Corporate Bond ETF",
        "asset_class": "IG Credit",
    },
    "SPSB": {
        "name": "SPDR Portfolio Short Term Corporate Bond ETF",
        "asset_class": "IG Credit",
    },
    "VCSH": {
        "name": "Vanguard Short-Term Corporate Bond ETF",
        "asset_class": "IG Credit",
    },

    # High Yield Credit
    "HYG": {
        "name": "iShares iBoxx $ High Yield Corporate Bond ETF",
        "asset_class": "HY Credit",
    },
    "JNK": {
        "name": "SPDR Bloomberg High Yield Bond ETF",
        "asset_class": "HY Credit",
    },
    "SJNK": {
        "name": "SPDR Bloomberg Short Term High Yield Bond ETF",
        "asset_class": "HY Credit",
    },
    "SHYG": {
        "name": "iShares 0-5 Year High Yield Corporate Bond ETF",
        "asset_class": "HY Credit",
    },

    # EM Debt
    "EMB": {
        "name": "iShares J.P. Morgan USD Emerging Markets Bond ETF",
        "asset_class": "EM Debt",
    },
    "VWOB": {
        "name": "Vanguard Emerging Markets Government Bond ETF",
        "asset_class": "EM Debt",
    },
    "PCY": {
        "name": "Invesco Emerging Markets Sovereign Debt ETF",
        "asset_class": "EM Debt",
    },

    # MBS / Securitized
    "MBB": {
        "name": "iShares MBS ETF",
        "asset_class": "MBS",
    },
    "VMBS": {
        "name": "Vanguard Mortgage-Backed Securities ETF",
        "asset_class": "MBS",
    },

    # Floating Rate / Short Credit
    "FLOT": {
        "name": "iShares Floating Rate Bond ETF",
        "asset_class": "Floating Rate",
    },
    "FLRN": {
        "name": "SPDR Bloomberg Investment Grade Floating Rate ETF",
        "asset_class": "Floating Rate",
    },

    # Municipals
    "MUB": {
        "name": "iShares National Muni Bond ETF",
        "asset_class": "Municipal",
    },
    "VTEB": {
        "name": "Vanguard Tax-Exempt Bond ETF",
        "asset_class": "Municipal",
    },
    "HYD": {
        "name": "VanEck High Yield Muni ETF",
        "asset_class": "Municipal",
    },
}

PERIOD_OPTIONS = {
    "5D": 5,
    "30D": 30,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}
