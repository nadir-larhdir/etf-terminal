# Notebooks

Starter notebooks for exploring ETF Terminal data and domain logic from Jupyter.

Suggested flow:

1. `00_setup_and_connections.ipynb`
   Connect to the repo data layer and inspect available stores.
2. `01_prices_and_returns.ipynb`
   Pull ETF prices and build return series.
3. `02_macro_series_and_features.ipynb`
   Explore raw macro series and derived macro features.
4. `03_fixed_income_analytics.ipynb`
   Run the fixed-income analytics service on one ETF.
5. `04_pair_trading_sandbox.ipynb`
   Prototype a simple HYG/JNK pair trade workflow.
6. `05_holdings_and_metadata.ipynb`
   Inspect stored ETF metadata and pull live ETF holdings from FMP.
7. `06_macro_regime_sandbox.ipynb`
   Explore macro feature combinations and build simple regime snapshots.
8. `07_backtest_template.ipynb`
   Use a simple pair-trade backtest template based on z-score entries/exits.
9. `08_macro_vs_etf_sensitivity.ipynb`
   Regress ETF returns on Treasury and OAS factor changes to inspect rate and spread sensitivities.

Typical backend choices:

- Local UAT:
  - `DATA_BACKEND = "local"`
  - `APP_ENV = "uat"`
- Supabase:
  - `DATA_BACKEND = "supabase"`

Open Jupyter from the repo root so imports like `from db.connection import get_engine` resolve cleanly.
