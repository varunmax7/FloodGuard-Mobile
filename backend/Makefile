.PHONY: run migrate makemigrations build-hexgrid load-fsi test lint format shell createsuperuser collectstatic

# ── Dev server ────────────────────────────────────────────────────────────────
run:
	python manage.py runserver 0.0.0.0:8000

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:
	python manage.py migrate --noinput

makemigrations:
	python manage.py makemigrations

# ── Geo management ───────────────────────────────────────────────────────────
build-hexgrid:
	python manage.py build_hexgrid

load-fsi:
	python manage.py load_fsi --layers $(LAYERS)

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	pytest tests/ --tb=short -q

test-v:
	pytest --tb=long -v

test-e2e:
	pytest tests/test_e2e.py --tb=short -v

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
