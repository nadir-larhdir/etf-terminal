# ETF Terminal

## Setup

```bash
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed_securities.py
python scripts/backfill_prices.py
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

- 📊 Bloomberg-style dashboard (Streamlit)
- 📈 Price analytics with mean & ±1σ bands
- 📉 Volume regime detection
- 🔄 Flow & premium/discount tracking
- 🧮 Relative value (RV) signals
- 🗂 SQL-based data storage (SQLite → scalable to PostgreSQL)

---

## 🏗 Architecture

The project follows a modular, scalable structure:

```text
models/        → financial instruments (ETF classes)
repositories/  → database access layer
services/      → market data + analytics
dashboard/     → UI & visualization (Streamlit)
scripts/       → DB setup & data ingestion
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
python scripts/init_db.py
python scripts/seed_securities.py
python scripts/backfill_prices.py
```

### 3. Run the dashboard

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