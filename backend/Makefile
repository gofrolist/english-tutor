.PHONY: install test lint typecheck format check run bot migrate setup-google-terraform clean pre-commit

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check

typecheck:
	uv run pyright

format:
	uv run ruff format .

check: lint typecheck

run:
	uv run python main.py

migrate:
	uv run alembic upgrade head

bot: migrate
	uv run python run_bot.py

setup-google-terraform:
	uv run python scripts/setup_google_terraform.py

setup-bot-menu:
	uv run python scripts/setup_bot_menu.py

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache htmlcov coverage.xml

pre-commit:
	uv run pre-commit run --all-files
