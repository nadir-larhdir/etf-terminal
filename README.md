# ETF Terminal

## Setup

```bash
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed_securities.py
python scripts/backfill_prices.py
streamlit run main.py
```
