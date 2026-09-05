.PHONY: run format lint fix test check

run:
	uv run python -m src

format:
	uv run ruff format .

lint:
	uv run ruff check .
	uv run mypy .

fix:
	uv run ruff check . --fix

test:
	uv run pytest

check:
	uv run pre-commit run --all-files
