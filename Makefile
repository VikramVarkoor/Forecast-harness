PY ?= python

.PHONY: setup data hourly audit plots test baselines clean

setup:
	$(PY) -m pip install -r requirements.txt

data:
	$(PY) src/download.py --start 2025-02 --months 12

hourly:
	$(PY) src/build_hourly.py

audit:
	$(PY) src/audit.py

plots:
	$(PY) src/plots.py

baselines:
	$(PY) src/run_baselines.py

test:
	$(PY) -m pytest -q

clean:
	rm -rf data/*.parquet results/*
