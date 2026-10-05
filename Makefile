# RefundAgent — thin wrapper over the AgentCore CLI.
#   make dev            # run the agent locally (chat UI on :8081)
#   make chat-deploy    # host the tester on a Lambda URL in the current account
export AWS_REGION ?= eu-central-1

.PHONY: help check dev chat-deploy chat-down
help:  ## show this help
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

check: ## verify the AgentCore CLI is installed and recognizes this project
	@command -v agentcore >/dev/null 2>&1 || { \
	  printf '\n  The AgentCore CLI is not installed.\n  Install it:  npm install -g @aws/agentcore\n\n'; exit 1; }
	@agentcore validate >/dev/null 2>&1 || { \
	  printf '\n  "agentcore" is installed but does not recognize this project.\n  You probably have the old Python CLI -- install the current one:\n    npm install -g @aws/agentcore\n\n'; exit 1; }

dev: check ## run the agent (foreground; chat UI :8081, API :8080). No Docker needed.
	agentcore dev --port 8080

# --- chat/ : the tester, one per AWS account (it finds that account's resources itself) ---
chat-deploy: ## deploy or update the tester on a public Lambda URL; prints the URL. OWNER=you sets the owner tag
	./chat/deploy.sh

chat-down: ## delete the tester's Lambda and role from this account
	-aws lambda delete-function --region $(AWS_REGION) --function-name agentcore-chat-ui
	-aws iam delete-role-policy --role-name agentcore-chat-ui-role --policy-name lookup-readonly
	-aws iam detach-role-policy --role-name agentcore-chat-ui-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
	-aws iam delete-role --role-name agentcore-chat-ui-role
