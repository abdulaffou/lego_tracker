VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup:
	python3 -m venv $(VENV)
	$(PIP) install -q -r requirements.txt

test:
	$(VENV)/bin/pytest -q

check:
	$(PY) -m legotracker.cli --local

run:
	$(PY) -m legotracker.cli
