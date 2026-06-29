.PHONY: install run api test
install:
	pip install -r requirements.txt
run:
	python examples/run_pipeline.py
api:
	uvicorn api.main:app --reload
test:
	pytest -q
