-include ~/.claude/Makefile

.PHONY: help env-dev env-run test test-cov test-all run format lint typecheck check build pre-publish publish publish-test clean clean-all

env-dev: ## Install all dependencies (dev + docs)
	uv sync --all-extras

env-run: ## Install runtime dependencies only
	uv sync --no-dev

test: ## Run tests (usage: make test TEST=file|file:test_name)
	@if [ -n "$(TEST)" ]; then \
		uv run pytest $(TEST); \
	else \
		uv run pytest; \
	fi

test-cov: ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html

test-all: ## Run tests on all Python versions
	uv run tox

run: ## Run the example application
	uv run python main.py

format: ## Format code and fix linting issues
	uv run ruff format src/
	uv run ruff check --fix src/

lint: ## Check code for linting issues
	uv run ruff check src/

typecheck: ## Run type checking
	uv run mypy src/

check: format lint typecheck test ## Run all quality checks

build: ## Build distribution packages
	uv build

pre-publish: check ## Pre-publication checks (run before publishing)
	@echo "Checking for relative image paths in README..."
	@grep -n '!\[.*](media/' README.md && (echo "ERROR: Relative image paths found - use raw GitHub URLs for PyPI"; exit 1) || echo "OK: No relative image paths"
	@echo "Checking version sync..."
	@VERSION_PY=$$(grep '^version =' pyproject.toml | cut -d'"' -f2); \
	VERSION_INIT=$$(grep '^__version__ = ' src/clevis/__init__.py | cut -d'"' -f2); \
	if [ "$$VERSION_PY" != "$$VERSION_INIT" ]; then \
		echo "ERROR: Version mismatch - pyproject.toml ($$VERSION_PY) vs __init__.py ($$VERSION_INIT)"; \
		exit 1; \
	fi; \
	echo "OK: Versions match ($$VERSION_PY)"
	@echo "Pre-publication checks passed"

publish: clean build ## Publish to PyPI (runs pre-publish checks)
	@$(MAKE) pre-publish
	uv run twine upload dist/*

publish-test: build ## Publish to TestPyPI
	uv run twine upload --repository testpypi dist/*

clean: ## Remove build artifacts
	rm -rf dist/ *.egg-info .pytest_cache .coverage htmlcov/ .mypy_cache .ruff_cache

clean-all: clean ## Remove virtualenv and lock file
	rm -rf .venv uv.lock


