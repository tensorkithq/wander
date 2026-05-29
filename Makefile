# Yugo body API — common dev tasks. Run `make` (or `make help`) to list them.
# The dog's IP is DHCP and changes per session, so pass it: `make serve IP=<dog-ip>`.
PY   := .venv/bin
HOST ?= 0.0.0.0
PORT ?= 8080

.DEFAULT_GOAL := help
.PHONY: help serve start offline test migrate

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  make %-9s %s\n", $$1, $$2}'

serve: ## Run with a robot + autoreload (dev):  make serve IP=192.168.202.107
	@test -n "$(IP)" || { echo "usage: make serve IP=<dog-ip>   (no dog? use: make offline)"; exit 2; }
	ROBOT_IP=$(IP) $(PY)/uvicorn yugo.main:app --host $(HOST) --port $(PORT) --reload

start: ## Run WITHOUT autoreload (prod-ish; uses robot.yaml IP, or pass IP=)
	ROBOT_IP=$(IP) $(PY)/python -m yugo --host $(HOST) --port $(PORT)

offline: ## Run with no dog — reflex layer (nav/deadman/state) only
	YUGO_NO_ROBOT=1 $(PY)/uvicorn yugo.main:app --host $(HOST) --port $(PORT) --reload

test: ## Run the test suite (pytest, no robot needed)
	uv run pytest

migrate: ## Apply DB migrations (alembic upgrade head)
	$(PY)/alembic upgrade head
