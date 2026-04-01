from datetime import datetime

from db.connection import get_engine
from repositories.metadata_repository import MetadataRepository


DEFAULT_METADATA = [
    {
        "ticker": "LQD",
        "conid": None,
        "long_name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "description": "Tracks a broad basket of USD-denominated investment grade corporate bonds and is commonly used as a liquid proxy for long-duration IG credit risk.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "Markit iBoxx USD Liquid Investment Grade Index",
        "category": "IG Credit",
        "duration_bucket": "Intermediate / Long Duration",
        "currency": "USD",
        "exchange": "NASDAQ",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "HYG",
        "conid": None,
        "long_name": "iShares iBoxx $ High Yield Corporate Bond ETF",
        "description": "Tracks USD-denominated high yield corporate bonds and is widely used as a liquid proxy for broad HY beta and risk sentiment.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "Markit iBoxx USD Liquid High Yield Index",
        "category": "HY Credit",
        "duration_bucket": "Intermediate Duration",
        "currency": "USD",
        "exchange": "NYSE Arca",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "IEF",
        "conid": None,
        "long_name": "iShares 7-10 Year Treasury Bond ETF",
        "description": "Tracks U.S. Treasury securities in the 7 to 10 year maturity bucket and is commonly used as a liquid belly-duration hedge.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "ICE U.S. Treasury 7-10 Year Bond Index",
        "category": "UST Belly",
        "duration_bucket": "7-10Y",
        "currency": "USD",
        "exchange": "NASDAQ",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "TLT",
        "conid": None,
        "long_name": "iShares 20+ Year Treasury Bond ETF",
        "description": "Tracks long-dated U.S. Treasury securities and is widely used as a liquid proxy for long duration and macro rate exposure.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "ICE U.S. Treasury 20+ Year Bond Index",
        "category": "UST Long",
        "duration_bucket": "20Y+",
        "currency": "USD",
        "exchange": "NASDAQ",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "AGG",
        "conid": None,
        "long_name": "iShares Core U.S. Aggregate Bond ETF",
        "description": "Tracks the broad U.S. investment grade bond market across Treasuries, agencies, MBS, and corporates and is often used as a core bond benchmark.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "Bloomberg U.S. Aggregate Bond Index",
        "category": "Core Bond",
        "duration_bucket": "Intermediate Duration",
        "currency": "USD",
        "exchange": "NYSE Arca",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
]


if __name__ == "__main__":
    engine = get_engine()
    repo = MetadataRepository(engine)
    repo.upsert_metadata(DEFAULT_METADATA)
    print("Security metadata seeded.")