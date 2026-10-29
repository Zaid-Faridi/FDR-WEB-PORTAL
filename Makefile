.PHONY: up down restart test seed logs build clean shell

# Default action starts all services via Docker Compose
up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d

build:
	docker compose build

logs:
	docker compose logs -f

# Run pytest backend test suite in container
test:
	docker compose run --rm backend pytest

# Seed 25 institutions and ~60 instruments covering all lifecycle scenarios
seed:
	@docker compose exec backend python manage.py seed_data 2>/dev/null || docker compose run --rm backend python manage.py seed_data

# Open backend shell
shell:
	docker compose run --rm backend python manage.py shell

# Clean up dangling containers and volumes
clean:
	docker compose down -v --remove-orphans
