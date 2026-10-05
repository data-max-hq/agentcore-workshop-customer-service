# RefundAgent — thin wrapper over the AgentCore CLI.
#   make dev            # run the agent locally (chat UI on :8081)
#   make infra-deploy   # optional: deploy the payment Gateway + Lambda to AWS
#   make ui-deploy      # host the chat UI on a Lambda URL in the current account
export AWS_REGION ?= eu-central-1

.PHONY: help check dev infra-preview infra-deploy infra-down ui-deploy ui-down
help:  ## show this help
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

check: ## verify the AgentCore CLI is installed and recognizes this project
	@command -v agentcore >/dev/null 2>&1 || { \
	  printf '\n  The AgentCore CLI is not installed.\n  Install it:  npm install -g @aws/agentcore\n\n'; exit 1; }
	@agentcore validate >/dev/null 2>&1 || { \
	  printf '\n  "agentcore" is installed but does not recognize this project.\n  You probably have the old Python CLI -- install the current one:\n    npm install -g @aws/agentcore\n\n'; exit 1; }

dev: check ## run the agent (foreground; chat UI :8081, API :8080). No Docker needed.
	agentcore dev --port 8080

# --- infra/ : optional payment Gateway + fake-payout Lambda (see infra/README.md) ---
infra-preview: check ## preview the AWS resources the gateway would create (no deploy, no spend)
	agentcore deploy --dry-run

infra-deploy: check ## deploy the payment Gateway + fake Lambda + Memory to AWS (creates real resources)
	agentcore deploy

infra-down: check ## tear the payment Gateway back down (removes from AWS)
	agentcore remove gateway --name PaymentGateway -y && agentcore deploy

# --- ui/ : hosted chat UI, one per AWS account (it finds that account's resources itself) ---
ui-deploy: ## deploy or update the chat UI on a public Lambda URL; prints the URL. OWNER=you sets the owner tag
	./ui/deploy.sh

ui-down: ## delete the chat UI's Lambda and role from this account
	-aws lambda delete-function --region $(AWS_REGION) --function-name agentcore-chat-ui
	-aws iam delete-role-policy --role-name agentcore-chat-ui-role --policy-name lookup-readonly
	-aws iam detach-role-policy --role-name agentcore-chat-ui-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
	-aws iam delete-role --role-name agentcore-chat-ui-role
