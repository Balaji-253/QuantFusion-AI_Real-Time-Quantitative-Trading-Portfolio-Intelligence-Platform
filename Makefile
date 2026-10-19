.PHONY: install run test lint up down logs
install:
	python -m pip install -r requirements.txt
run:
	uvicorn app.main:app --reload
test:
	pytest -q
up:
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f api
