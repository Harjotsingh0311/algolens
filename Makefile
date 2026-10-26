.PHONY: install check test ingest review-check index eval app release

install:
	uv sync --all-groups

check:
	uv lock --check
	uv run ruff check src tests app
	uv run ruff format --check src tests app
	uv run mypy src

test:
	uv run pytest -q

ingest:
	uv run python -m algolens.cli ingest

review-check:
	uv run python -m algolens.cli review-check

index:
	uv run python -m algolens.cli index

eval:
	uv run python -m algolens.cli eval

app:
	uv run python app/app.py

release:
	@echo "Release automation will be enabled after evaluation and deployment are implemented."
