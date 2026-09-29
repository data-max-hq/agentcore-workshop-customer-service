# agentcore-workshop-customer-service

Sample app for the Amazon Bedrock AgentCore workshop — a customer-support
**refund agent** that runs entirely locally and is built to be broken on purpose.

The agent lives in [`RefundAgent/`](RefundAgent/README.md). Start there: it has
the architecture, the four failure seams, and the run steps.

```bash
cd RefundAgent
make up      # DynamoDB Local + seed demo orders
make dev     # the agent — leave running
make demo    # prove all four seams (in a third terminal)
```

Nothing is deployed to AWS — state is DynamoDB Local (Docker), and only the model
runs in the cloud (Bedrock). See [`RefundAgent/README.md`](RefundAgent/README.md).
