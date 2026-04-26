.PHONY: run run-local run-supabase refresh test lint fmt check

run:
	streamlit run main.py

run-local:
	DATA_BACKEND=local APP_ENV=uat streamlit run main.py

run-supabase:
	DATA_BACKEND=supabase APP_ENV=uat streamlit run main.py

refresh:
	python -m scripts.daily.refresh_all --backend supabase --app-env uat

refresh-force:
	python -m scripts.daily.refresh_all --backend supabase --app-env uat --force-analytics

test:
	pytest

lint:
	ruff check .

fmt:
	black .

check:
	ruff check . && black --check .
