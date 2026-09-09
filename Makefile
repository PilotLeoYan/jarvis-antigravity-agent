.PHONY: run format lint fix test check install

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

install:
	uv sync
	mkdir -p $(HOME)/.local/bin
	ln -sf $(CURDIR)/.venv/bin/jarvis-antigravity-agent $(HOME)/.local/bin/jarvis-antigravity-agent
	ln -sf $(CURDIR)/.venv/bin/jarvis-send-message $(HOME)/.local/bin/jarvis-send-message
	ln -sf $(CURDIR)/.venv/bin/jarvis-spawn-agent $(HOME)/.local/bin/jarvis-spawn-agent
	ln -sf $(CURDIR)/.venv/bin/jarvis-mcp $(HOME)/.local/bin/jarvis-mcp
	ln -sf $(CURDIR)/.venv/bin/jarvis-update $(HOME)/.local/bin/jarvis-update
	ln -sf $(CURDIR)/.venv/bin/jarvis-uninstall $(HOME)/.local/bin/jarvis-uninstall
