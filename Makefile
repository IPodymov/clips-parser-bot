VENV := .venv/bin
PY_SRC := src tests

.PHONY: venv install up down logs ps migrate revision lint format typecheck test check

venv:
	python3.12 -m venv .venv

install:
	$(VENV)/pip install -r requirements-dev.txt

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100 bot worker

ps:
	docker compose ps

# Runs from the host against postgres exposed on localhost:5433
migrate:
	$(VENV)/alembic upgrade head

# Usage: make revision m="add payments"
revision:
	$(VENV)/alembic revision --autogenerate -m "$(m)"

lint:
	$(VENV)/ruff check --fix $(PY_SRC)
	$(VENV)/ruff format $(PY_SRC)

format:
	$(VENV)/ruff format $(PY_SRC)

typecheck:
	$(VENV)/mypy src

test:
	$(VENV)/pytest

check: lint typecheck test
