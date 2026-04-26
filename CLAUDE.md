# ETF Terminal — Claude Context

Fixed income ETF analytics app built with Streamlit. Uses FMP for ETF prices/metadata, FRED for macro series, and supports local SQLite or Supabase/Postgres as the data backend.

## Layer order (always modify bottom-up)
config → db → stores → services → dashboard → scripts

## Running the app
```bash
make run-local     # SQLite UAT
make run-supabase  # Supabase UAT
```

## Running tests
```bash
make test
```

## Linting and formatting
```bash
make check   # ruff + black (read-only)
make lint    # ruff only
make fmt     # black (writes)
```

## Data refresh
```bash
make refresh        # daily refresh via Supabase
make refresh-force  # force recompute all analytics snapshots
```

## Key files
- `config/config.json` — DEFAULT_TICKERS universe, RSS feeds
- `services/market/duration_estimator.py` — iShares CSV duration logic and proxy/curve fallbacks
- `services/macro/macro_feature_service.py` — FEATURE_METADATA and all derived macro features
- `scripts/daily/refresh_all.py` — orchestrates the full daily pipeline

## Backend config
Set via env vars: `DATA_BACKEND=local|supabase`, `APP_ENV=uat|prod`.
Copy `.env.example` to `.env` and fill in API keys before running.

## Branches
- `uat` — active development
- `main` — stable, PR target
