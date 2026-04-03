# ETF Terminal

## Setup

```bash
pip install -r requirements.txt
APP_ENV=uat python3 -m scripts.db.initialize_database
APP_ENV=uat python3 -m scripts.market.sync_securities_universe
APP_ENV=uat python3 -m scripts.market.sync_price_history
streamlit run main.py
```

# ETF Terminal

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Database](https://img.shields.io/badge/database-SQLite-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 👤 About

**Nadir Larhdir**  
Systematic Credit Trader (Investment Grade) with a strong focus on fixed income markets and ETF dynamics.

This project reflects a personal initiative to build an **independent, production-style analytical tool** for trading fixed income ETFs.

---

## 🎯 Purpose

The objective of this project is to develop a **fully functional ETF trading dashboard** that provides actionable analytics for fixed income ETFs.

It is designed to support both:
- **Discretionary trading decisions**
- **Systematic analysis frameworks**

Key capabilities:
- Monitor price action and volume dynamics
- Analyze ETF flows and liquidity regimes
- Evaluate premium/discount vs underlying
- Generate structured trading commentary

---

## 🧠 Key Features

- 📊 Terminal-style dashboard (Streamlit)
- 📈 Price analytics with mean & ±1σ bands
- 📉 Volume regime detection
- 🔄 Flow & premium/discount tracking
- 🧮 Relative value (RV) signals
- 🗂 SQL-based data storage (SQLite → scalable to PostgreSQL)

---

## 🏗 Architecture

The project follows a modular, scalable structure:

```text
config/        → config.json + thin Python loader
db/            → engine + schema
models/        → financial instruments (ETF classes)
stores/  → data access layer grouped by domain
services/      → business logic grouped by domain
dashboard/     → app shell, components, tabs, and styles
scripts/       → CLI entrypoints grouped by domain (db / market / admin)
```

Design principles:
- Separation of concerns
- Database as single source of truth
- Extensibility for new data sources
- Clean OOP structure

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize database

```bash
APP_ENV=uat python3 -m scripts.db.initialize_database
APP_ENV=uat python3 -m scripts.market.sync_securities_universe
APP_ENV=uat python3 -m scripts.market.sync_price_history
```

Environment notes:
- `APP_ENV=prod` uses `market_data_prod.db`
- `APP_ENV=uat` uses `market_data_uat.db`
- if `APP_ENV` is omitted, the app defaults to `prod`

### 2b. Choose the right update mode

```bash
# Universe updates
APP_ENV=uat python3 -m scripts.market.sync_securities_universe --mode upsert
APP_ENV=uat python3 -m scripts.market.sync_securities_universe --mode missing-only

# Price updates
APP_ENV=uat python3 -m scripts.market.sync_price_history --mode incremental
APP_ENV=uat python3 -m scripts.market.sync_price_history --mode missing-only
APP_ENV=uat python3 -m scripts.market.sync_price_history --mode gap-fill --period 1y --tickers LQD,HYG
APP_ENV=uat python3 -m scripts.market.sync_price_history --mode full --period 5y --tickers TLT

# Metadata updates
APP_ENV=uat python3 -m scripts.market.sync_static_metadata --mode missing-only
APP_ENV=uat python3 -m scripts.market.enrich_metadata_from_fmp --mode upsert --tickers LQD,HYG

# Ticker management
APP_ENV=uat python3 -m scripts.admin.manage_universe_ticker add BSV
APP_ENV=uat python3 -m scripts.admin.manage_universe_ticker delete BSV
```

- `full` / `full-replace`: delete and reload the selected scope.
- `gap-fill`: refetch a period and upsert it without deleting existing rows.
- `incremental`: fetch only recent data from the latest stored date forward.
- `missing-only`: only insert rows for tickers that are not already in the database.

### 3. Run the dashboard

```bash
APP_ENV=uat streamlit run main.py
APP_ENV=prod streamlit run main.py
```

or simply:

```bash
streamlit run main.py
```

---

## 🔁 Workflow (Git)

- `main` → stable / production version
- `uat` → testing & development

Typical flow:

```bash
git checkout uat
# develop features
git push

# then via PR → merge into main
```

---

## 🛣 Roadmap

- [ ] Replace external data calls with full SQL pipeline
- [ ] Persist user inputs (flows, notes, prem/discount)
- [ ] Add advanced liquidity & RV metrics
- [ ] Introduce signal generation framework
- [ ] Add backtesting module
- [ ] Integrate broker / API data sources

---

## ⚠️ Disclaimer

This tool is for **research and educational purposes only**.  
It does not constitute financial advice or a recommendation to trade.

---

## 💡 Vision

The long-term ambition is to build a **compact, trader-grade analytics terminal** for fixed income ETFs — bridging discretionary insight and systematic modeling in a single interface.
