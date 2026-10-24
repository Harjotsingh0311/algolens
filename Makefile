.PHONY: install check test ingest index eval app release

install:
	uv sync --all-groups

check:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src

test:
	uv run pytest -q

ingest:
	uv run python -m algolens.cli ingest

index:
	uv run python -m algolens.cli index

eval:
	uv run python -m algolens.cli eval

app:
	uv run python app/app.py

release:
	@echo "Release automation will be enabled after evaluation and deployment are implemented."
