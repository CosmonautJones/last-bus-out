.PHONY: setup data run test
setup:   ## install dependencies
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
data:    ## download public data + build lookup tables
	python scripts/fetch_data.py && python scripts/build_index.py
run:     ## start the app on http://localhost:8000
	set -a; [ -f .env ] && . ./.env; set +a; uvicorn app.main:app --reload --port 8000
test:
	python -m pytest -q tests
