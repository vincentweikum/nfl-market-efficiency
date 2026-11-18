.PHONY: all data build analysis test lint

all: build analysis test

data:            ## pull the latest games from nflverse
	python ingest.py

build:           ## dbt models + data tests
	cd dbt && dbt build --profiles-dir .

analysis:        ## stats, charts, findings.json
	python -m analysis.run_analysis

test:
	pytest -q

lint:
	ruff check .
