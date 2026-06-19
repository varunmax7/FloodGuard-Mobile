.PHONY: run migrate makemigrations test lint format shell createsuperuser collectstatic

# ── Dev server ────────────────────────────────────────────────────────────────
run:
	python manage.py runserver 0.0.0.0:8000

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:
	python manage.py migrate --noinput

makemigrations:
	python manage.py makemigrations

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	pytest --tb=short -q

test-v:
	pytest --tb=long -v

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	flake8 . --max-line-length=120 --exclude=migrations,__pycache__

format:
	black . --line-length=120 --exclude='migrations|__pycache__'

# ── Django shell ──────────────────────────────────────────────────────────────
shell:
	python manage.py shell

# ── Admin user ────────────────────────────────────────────────────────────────
createsuperuser:
	python manage.py createsuperuser

# ── Static files ──────────────────────────────────────────────────────────────
collectstatic:
	python manage.py collectstatic --noinput

# ── Docker convenience ────────────────────────────────────────────────────────
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f
