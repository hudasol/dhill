.PHONY: install test lint fmt serve demo docs
install:
	pip install -e ".[dev]"
test:
	pytest -q
lint:
	ruff check . && ruff format --check .
fmt:
	ruff check --fix . && ruff format .
serve:
	dhill serve
demo:
	dhill timeline --site sweihan --scenario heatwave --step-min 60
	dhill plan --robots ugv_medium_inspection sidewalk_delivery_robot
docs:
	python scripts/gen_parameters_doc.py
