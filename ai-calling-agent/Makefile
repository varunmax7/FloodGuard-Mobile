# FloodGuard Voice Agent — developer commands.
# Every command must work on a fresh clone with only `uv` and Docker installed.

.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

PY := uv run
COMPOSE := docker compose

# ── environment ─────────────────────────────────────────────────────
export FG_ENV ?= dev
export PYTHONDONTWRITEBYTECODE := 1
export PYTHONUNBUFFERED := 1

.PHONY: help
help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS=":.*?## "} {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── setup / stack ───────────────────────────────────────────────────
.PHONY: install
install:  ## install python deps into a uv-managed .venv
	uv sync --all-extras

.PHONY: dev
dev:  ## boot local stack (postgres+postgis+pgvector, redis, localstack)
	$(COMPOSE) up -d
	@echo "→ postgres:   localhost:55432 (fg_voice / fg_voice / fg_voice)"
	@echo "→ redis:      localhost:56379"
	@echo "→ localstack: http://localhost:54566"
	@echo "→ run 'make api' or 'make agent' to start a service"

.PHONY: down
down:  ## stop local stack
	$(COMPOSE) down

.PHONY: nuke
nuke:  ## stop local stack AND wipe volumes (destructive)
	$(COMPOSE) down -v

.PHONY: api
api:  ## run the webhook + reports API
	$(PY) uvicorn fg_voice.main:app --host 0.0.0.0 --port 8080 --reload

.PHONY: agent
agent:  ## run a voice-agent worker (P1+)
	$(PY) uvicorn fg_voice.main:app --host 0.0.0.0 --port 8081

# ── quality gates ───────────────────────────────────────────────────
.PHONY: lint
lint:  ## ruff + mypy + import-linter contracts
	$(PY) ruff check .
	$(PY) ruff format --check .
	$(PY) mypy src
	$(PY) lint-imports

.PHONY: fmt
fmt:  ## auto-format
	$(PY) ruff format .
	$(PY) ruff check --fix .

.PHONY: test
test:  ## unit + property (fast; runs in CI)
	$(PY) pytest tests/unit tests/property -m "not slow"

.PHONY: test-all
test-all:  ## everything including integration/golden/noise
	$(PY) pytest

.PHONY: golden
golden:  ## audio → slot regression (P3+)
	$(PY) pytest tests/golden -v

.PHONY: noise
noise:  ## SNR sweep report (P3+)
	$(PY) pytest tests/noise -v --html=reports/noise.html --self-contained-html

.PHONY: bench
bench:  ## latency budget assertion (P4+)
	$(PY) python scripts/bench_latency.py --calls 200 --turns 8

.PHONY: sim
sim:  ## persona simulation suite (P8+)
	$(PY) python scripts/simulate_call.py --all-personas

.PHONY: audit
audit:  ## dependency vulnerability scan
	$(PY) pip-audit

# ── artifacts ───────────────────────────────────────────────────────
.PHONY: render-bank
render-bank:  ## rerender the prerendered TTS audio bank
	$(PY) python scripts/render_audio_bank.py --locale en-IN

.PHONY: build-gazetteer
build-gazetteer:  ## build the gazetteer FAISS snapshot (P4+)
	$(PY) python scripts/build_gazetteer.py

# ── migrations ──────────────────────────────────────────────────────
.PHONY: migrate-current
migrate-current:  ## show the current DB revision
	$(PY) alembic current

.PHONY: migrate-upgrade
migrate-upgrade:  ## apply all pending migrations
	$(PY) alembic upgrade head

.PHONY: migrate-revision
migrate-revision:  ## generate a new autogen migration (usage: make migrate-revision m="add x")
	@if [ -z "$(m)" ]; then echo 'usage: make migrate-revision m="short message"'; exit 1; fi
	$(PY) alembic revision --autogenerate -m "$(m)"

# ── deploy ──────────────────────────────────────────────────────────
.PHONY: deploy
deploy:  ## deploy to $ENV (staging | prod) via terraform (P7+)
	@if [ -z "$(ENV)" ]; then echo "usage: make deploy ENV=staging"; exit 1; fi
	cd infra/terraform && terraform workspace select $(ENV) \
	  && terraform apply -var-file=envs/$(ENV).tfvars

.PHONY: clean
clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	rm -rf reports/ .coverage htmlcov/
