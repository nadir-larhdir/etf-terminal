PYTHON ?= python
STREAMLIT ?= streamlit
PYTEST ?= pytest
RUFF ?= ruff
BLACK ?= black

.PHONY: run run-local run-supabase refresh refresh-force test lint fmt check clean

run:
	$(STREAMLIT) run main.py

run-local:
	DATA_BACKEND=local APP_ENV=uat $(STREAMLIT) run main.py

run-supabase:
	DATA_BACKEND=supabase APP_ENV=uat $(STREAMLIT) run main.py

refresh:
	$(PYTHON) -m scripts.daily.refresh_all --backend supabase --app-env uat

refresh-force:
	$(PYTHON) -m scripts.daily.refresh_all --backend supabase --app-env uat --force-analytics

test:
	$(PYTEST)

lint:
	$(RUFF) check .

fmt:
	$(BLACK) .

check:
	$(RUFF) check . && $(BLACK) --check .

clean:
	find . \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \) -prune -exec rm -rf {} +
	find . \( -name '*.pyc' -o -name '.DS_Store' \) -type f -delete
