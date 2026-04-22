# ETF Terminal

ETF Terminal is a fixed income ETF analytics application built with Streamlit.
It combines ETF price history from Financial Modeling Prep, macro time series from FRED, a database-backed dashboard, relative value analysis, and a market news layer in one workflow.

This README is written as an operating guide rather than a project summary. The goal is to make it easy to:
- run the app
- update the data
- manage tickers
- switch between local and Supabase backends
- extend the project safely over time

**Overview**

ETF Terminal is organized around five layers:

```text
config/     application settings and environment loading
db/         engine, schema, SQL helpers
stores/     database read/write access
services/   provider clients and business logic
dashboard/  Streamlit UI, tabs, components, styles
scripts/    command-line entrypoints for setup and data operations
```

The app currently supports:
- ETF end-of-day prices from FMP
- ETF metadata from FMP
- macro series from FRED
- derived macro features
- local SQLite or Supabase/Postgres as the data backend

**Prerequisites**

- Python 3.10+
- A working virtual environment
- FMP API key
- FRED API key
- Optional: Supabase Postgres connection string

Install dependencies:

```bash
pip install -r requirements.txt
```

**Environment Configuration**

Create a `.env` file in the project root.

Minimum setup:

```env
FMP_API_KEY=your_fmp_key
FRED_API_KEY=your_fred_key
DATA_BACKEND=local
APP_ENV=uat
```

Supabase setup:

```env
FMP_API_KEY=your_fmp_key
FRED_API_KEY=your_fred_key
DATA_BACKEND=supabase
APP_ENV=uat
SUPABASE_SCHEMA=public
SUPABASE_DB_URL=postgresql+psycopg2://postgres.<project_ref>:<password>@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require
```

Important notes:
- `DATA_BACKEND=local` uses SQLite files in the repo
- `DATA_BACKEND=supabase` uses Supabase/Postgres
- `APP_ENV=uat` and `APP_ENV=prod` still matter for local SQLite
- for Supabase, the app now uses one explicit schema: `public`

**Backends**

Local SQLite files:
- `market_data_uat.db`
- `market_data_prod.db`

Supabase:
- uses the `public` schema
- requires a working pooler connection string

Typical choices:

```bash
# Local development
DATA_BACKEND=local APP_ENV=uat streamlit run main.py

# Supabase-backed app
DATA_BACKEND=supabase APP_ENV=uat streamlit run main.py
```

**Initial Setup**

If you are starting from scratch with local SQLite:

```bash
python -m scripts.db.initialize_database
python -m scripts.market.sync_securities_universe --mode upsert
python -m scripts.market.sync_price_history --mode full --period 3y
python -m scripts.market.enrich_metadata_from_fmp --mode upsert
python -m scripts.macro.sync_macro_data --mode full --start 2000-01-01
python -m scripts.macro.build_macro_features
```

If you are setting up Supabase:

```bash
python -m scripts.db.initialize_database
python -m scripts.db.migrate_local_to_supabase --source-env uat
```

That copies the selected local SQLite environment into Supabase `public`.

**Run The App**

Standard launch:

```bash
streamlit run main.py
```

Explicit local launch:

```bash
DATA_BACKEND=local APP_ENV=uat streamlit run main.py
```

Explicit Supabase launch:

```bash
DATA_BACKEND=supabase APP_ENV=uat streamlit run main.py
```

**Daily Operating Commands**

These are the commands you are most likely to use regularly.

Run the full daily refresh in one command:

```bash
python -m scripts.daily.refresh_all --backend supabase --app-env uat
```

That workflow now does all of the following in order:
- sync the configured securities universe
- refresh ETF prices from FMP
- refresh FRED macro series
- rebuild macro features
- refresh ETF metadata, including issuer and duration
- recompute analytics snapshots when price dates or metadata durations changed

If you want to force all analytics snapshots to refresh:

```bash
python -m scripts.daily.refresh_all --backend supabase --app-env uat --force-analytics
```

Update ETF prices to the latest available FMP end-of-day data:

```bash
python -m scripts.market.sync_price_history --mode incremental
```

Safer recent overlap refresh:

```bash
python -m scripts.market.sync_price_history --mode incremental --overlap-days 2
```

Backfill a longer ETF history window:

```bash
python -m scripts.market.sync_price_history --mode full --period 3y
```

Update FRED macro series:

```bash
python -m scripts.macro.sync_macro_data --mode incremental
```

Update only Treasury series:

```bash
python -m scripts.macro.sync_macro_data --mode incremental --series DGS3MO,DGS6MO,DGS1,DGS2,DGS3,DGS5,DGS7,DGS10,DGS20,DGS30
```

Rebuild derived macro features:

```bash
python -m scripts.macro.build_macro_features
```

Refresh ETF metadata from FMP:

```bash
python -m scripts.market.enrich_metadata_from_fmp --mode upsert
```

**Ticker Management**

Add a ticker to the managed universe:

```bash
python -m scripts.admin.manage_universe_ticker add BSV
```

Add with an asset class override:

```bash
python -m scripts.admin.manage_universe_ticker add BSV --asset-class "Core Bond"
```

Delete a ticker everywhere:

```bash
python -m scripts.admin.manage_universe_ticker delete BSV
```

Ticker deletion removes the symbol from:
- `securities`
- `security_metadata`
- `price_history`
- `security_inputs`

**Universe Management**

The current universe is still driven by `DEFAULT_TICKERS` in `config/config.json`.

To sync that static universe into the database:

```bash
python -m scripts.market.sync_securities_universe --mode upsert
```

To fully replace the existing universe with the config universe:

```bash
python -m scripts.market.sync_securities_universe --mode full-replace
```

Use full replace carefully.

**Metadata Workflow**

Static metadata and FMP-enriched metadata serve different roles:

- `sync_static_metadata` seeds curated internal descriptions and fixed-income-specific fields
- `enrich_metadata_from_fmp` merges provider fields such as AUM, exchange, quote type, and expense ratio

Recommended flow:

```bash
python -m scripts.market.sync_static_metadata --mode missing-only
python -m scripts.market.enrich_metadata_from_fmp --mode upsert
```

**Macro Workflow**

Macro data is separated into two layers:

1. `macro_data`
   raw FRED time series
2. `macro_features`
   derived analytics used by the Macro tab

Normal workflow:

```bash
python -m scripts.macro.sync_macro_data --mode incremental
python -m scripts.macro.build_macro_features
```

**Common Workflows**

Run the app locally against SQLite:

```bash
DATA_BACKEND=local APP_ENV=uat streamlit run main.py
```

Run the app against Supabase:

```bash
DATA_BACKEND=supabase APP_ENV=uat streamlit run main.py
```

Refresh all data before market review:

```bash
python -m scripts.market.sync_price_history --mode incremental --overlap-days 2
python -m scripts.macro.sync_macro_data --mode incremental
python -m scripts.macro.build_macro_features
python -m scripts.market.enrich_metadata_from_fmp --mode upsert
```

Initialize a fresh UAT local database:

```bash
DATA_BACKEND=local APP_ENV=uat python -m scripts.db.initialize_database
DATA_BACKEND=local APP_ENV=uat python -m scripts.market.sync_securities_universe --mode upsert
DATA_BACKEND=local APP_ENV=uat python -m scripts.market.sync_price_history --mode full --period 3y
DATA_BACKEND=local APP_ENV=uat python -m scripts.market.enrich_metadata_from_fmp --mode upsert
DATA_BACKEND=local APP_ENV=uat python -m scripts.macro.sync_macro_data --mode full --start 2000-01-01
DATA_BACKEND=local APP_ENV=uat python -m scripts.macro.build_macro_features
```

Migrate local UAT into Supabase:

```bash
DATA_BACKEND=supabase APP_ENV=uat python -m scripts.db.initialize_database
DATA_BACKEND=supabase APP_ENV=uat python -m scripts.db.migrate_local_to_supabase --source-env uat
```

**How The App Is Structured**

Main sections of the UI:
- `Home`
- `Dashboard`
- `News`
- `Macro`

Dashboard tabs:
- `Graphs`
- `Analytics`
- `RV Analysis`

What each section is for:

- `Home`
  general framing of the project and universe snapshot
- `Dashboard`
  single-name ETF analysis
- `News`
  live rates, credit, ETF, and macro headlines
- `Macro`
  Treasury curve, macro features, and regime summary

**How To Extend The App**

When improving the app, use this order of operations:

1. Decide which layer the change belongs to
- `config` for settings
- `db` for schema or SQL helpers
- `stores` for read/write logic
- `services` for provider integration or feature logic
- `dashboard` for UI
- `scripts` for CLI entrypoints

2. Update the smallest layer first
- schema before stores
- stores before services
- services before dashboard

3. Keep provider logic separate
- FMP for ETF data
- FRED for macro data
- dashboard should consume stores/services, not raw providers directly

4. Prefer existing workflows
- if you are changing market data, look at `scripts.market.sync_price_history`
- if you are changing macro data, look at `scripts.macro.sync_macro_data` and `scripts.macro.build_macro_features`
- if you are changing ticker lifecycle, look at `scripts.admin.manage_universe_ticker`

5. After any change, test with the real backend you use most
- local if you are developing schema logic
- Supabase if you are validating production-style behavior

**Useful Checks**

Verify local database counts:

```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("market_data_uat.db")
cur = conn.cursor()
for table in ["securities", "price_history", "security_metadata", "macro_data", "macro_features"]:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(table, cur.fetchone()[0])
conn.close()
PY
```

Verify Supabase public tables:

```sql
select table_schema, table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;
```

Verify Supabase row counts:

```sql
select count(*) from public.securities;
select count(*) from public.price_history;
select count(*) from public.security_metadata;
select count(*) from public.macro_data;
select count(*) from public.macro_features;
```

**Branch Workflow**

Current working pattern:
- `uat` for ongoing development and testing
- `main` for the stable branch

Typical process:

```bash
git checkout uat
# make changes
git add .
git commit -m "Your change"
git push origin uat
```

Then open a PR from `uat` into `main`.

**Current Data Sources**

- ETF prices: Financial Modeling Prep
- ETF metadata: Financial Modeling Prep plus internal overrides
- Macro data: FRED
- News: RSS feeds configured in `config/config.json`

**Notes**

- The app is designed for research and workflow support, not for order execution
- FRED daily Treasury series can lag same-day market closes
- FMP end-of-day bars may also lag until the final daily bar is published
- Supabase now uses `public` explicitly to avoid pooler/search-path ambiguity

**Maintenance Checklist**

When something feels wrong, check these first:

1. Is the backend correct?
- `DATA_BACKEND=local` or `DATA_BACKEND=supabase`

2. Is the app using the intended environment?
- `APP_ENV=uat` or `APP_ENV=prod`

3. Are prices up to date?
- run `sync_price_history --mode incremental`

4. Are macro series up to date?
- run `sync_macro_data --mode incremental`

5. Were macro features rebuilt after macro updates?
- run `build_macro_features`

6. Is metadata stale or incomplete?
- run `enrich_metadata_from_fmp --mode upsert`
