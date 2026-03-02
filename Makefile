.PHONY: install test test-unit test-integration test-cov lint typecheck format check clean

install:
	pip install -e ".[dev]" --break-system-packages

test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/unit/ -v -m "not integration"

test-integration:
	python -m pytest tests/integration/ -v -m integration

test-cov:
	python -m pytest tests/ -v --cov=kindle_calibre --cov-report=term-missing --cov-report=html

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

typecheck:
	mypy src/kindle_calibre/

check: lint typecheck test
	@echo "✅ All checks passed"

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
