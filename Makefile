.PHONY: up down logs test smoke
up:
	sh scripts/setup.sh
down:
	docker compose down
logs:
	docker compose logs -f --tail=50 api worker
test:
	cd backend && ../.venv/bin/pytest -m 'not sandbox'
	cd frontend && npm run check && npm run build
smoke:
	.venv/bin/python scripts/smoke.py

