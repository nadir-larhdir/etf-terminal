# ETF Terminal - ChatGPT Context

Fixed income ETF analytics app built with Streamlit. Uses FMP for ETF prices/metadata, FRED for macro series, RSS feeds for market news, and supports local SQLite or Supabase/Postgres as the data backend.

## Working style
- Read the surrounding layer before editing.
- Respect the current dirty worktree; do not revert unrelated user changes.
- Prefer small, repo-patterned changes over broad refactors.
- Use Python 3.11+ for commands; this project is not compatible with older system Python versions.

## Layer order
Modify bottom-up when possible:

```text
config -> db -> stores -> services -> dashboard -> scripts
```

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
make clean   # remove local Python/macOS cache artifacts
```

## Data refresh
```bash
make refresh        # daily refresh via Supabase
make refresh-force  # force recompute all analytics snapshots
```

## Key files
- `config/config.json` - DEFAULT_TICKERS universe, macro registry, RSS feeds
- `db/connection.py` - local SQLite vs Supabase/Postgres engine setup
- `db/schema.py` - table definitions and incremental schema helpers
- `stores/` - database read/write access
- `services/market/duration_estimator.py` - iShares CSV duration logic and proxy/curve fallbacks
- `services/macro/macro_feature_service.py` - FEATURE_METADATA and derived macro features
- `services/news/news_feed_service.py` - RSS fetching/filtering for the News page
- `fixed_income/analytics/fixed_income_analytics_service.py` - rate/spread analytics pipeline
- `dashboard/dashboard_app.py` - Streamlit app shell and page routing
- `dashboard/pages/news_page.py` - Bloomberg-style market news page
- `scripts/daily/refresh_all.py` - full daily data/analytics pipeline

## Backend config
Set via env vars: `DATA_BACKEND=local|supabase`, `APP_ENV=uat|prod`.
Copy `.env.example` to `.env` and fill in API keys before running.

Local SQLite databases:
- `market_data_uat.db` - committed local UAT seed database for pull-and-run development
- `market_data_prod.db` - ignored local production database

Supabase uses the configured `SUPABASE_DB_URL` and schema, normally `public`.

## Pull-and-run local setup
```bash
cp .env.example .env
make run-local
```

The default example env points at `DATA_BACKEND=local` and `APP_ENV=uat`, so the app connects to the committed `market_data_uat.db`.

## Branches
- `uat` - active development
- `main` - stable, PR target
