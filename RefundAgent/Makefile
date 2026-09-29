# RefundAgent — thin wrapper over the commands in README.md.
# The agent runs in the foreground, so it needs its own terminal:
#   terminal 1:  make up        # state (once)
#   terminal 2:  make dev       # the agent (leave running)
#   terminal 3:  make demo      # prove the seams
export DDB_ENDPOINT ?= http://localhost:8000
export AWS_REGION   ?= us-east-1
APP := app/RefundAgent

.PHONY: help up seed dev demo verify down
help:  ## show this help
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

up: ## start DynamoDB Local and seed demo orders
	docker compose up -d
	$(MAKE) seed

seed: ## (re)create tables + seed demo orders
	cd $(APP) && uv run python seed.py

dev: ## run the agent (foreground; chat UI :8081, API :8080)
	cd $(APP) && agentcore dev --port 8080

demo: ## exercise and assert all four seams (needs `make dev` running)
	./demo.sh

verify: ## run the no-server logic checks (seams 1, 2 & 4)
	cd $(APP) && uv run python payment_gateway.py && uv run python store.py

down: ## stop DynamoDB Local (wipes its in-memory tables)
	docker compose down
