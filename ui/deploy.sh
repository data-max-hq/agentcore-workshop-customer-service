#!/usr/bin/env bash
# Deploy (or update) the hosted chat UI into whatever account your AWS credentials point at.
# Easiest: open AWS CloudShell (top bar of the AWS console) and run
#   git clone https://github.com/data-max-hq/agentcore-workshop-customer-service && bash agentcore-workshop-customer-service/ui/deploy.sh
# Usage: ./deploy.sh            (region defaults to eu-central-1)
#        OWNER=you ./deploy.sh  (value for the owner tag some accounts require)
set -euo pipefail
cd "$(dirname "$0")"
REGION=${AWS_REGION:-eu-central-1} FN=agentcore-chat-ui ROLE=agentcore-chat-ui-role
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ZIP=$(mktemp -d)/ui.zip && python3 -m zipfile -c "$ZIP" lambda_function.py

if ! aws iam get-role --role-name $ROLE >/dev/null 2>&1; then
  aws iam create-role --role-name $ROLE --output text --query Role.Arn --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
  aws iam attach-role-policy --role-name $ROLE --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
fi
# read-only: just enough for /lookup to find an attendee's resources by name
aws iam put-role-policy --role-name $ROLE --policy-name lookup-readonly --policy-document \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["cognito-idp:ListUserPools","cognito-idp:ListUserPoolClients","bedrock-agentcore:ListHarnesses","bedrock-agentcore:ListGateways"],"Resource":"*"}]}'

if aws lambda get-function --region $REGION --function-name $FN >/dev/null 2>&1; then
  aws lambda update-function-code --region $REGION --function-name $FN --zip-file "fileb://$ZIP" >/dev/null
else
  # a brand-new role takes a few seconds before Lambda may assume it, so retry
  for i in 1 2 3 4 5 6; do
    aws lambda create-function --region $REGION --function-name $FN --runtime python3.13 \
      --handler lambda_function.lambda_handler --role arn:aws:iam::$ACCOUNT:role/$ROLE \
      --timeout 15 --memory-size 256 --tags owner=${OWNER:-workshop} --zip-file "fileb://$ZIP" >/dev/null && break
    [ $i = 6 ] && exit 1; echo "waiting for the new role..."; sleep 5
  done
  aws lambda wait function-active-v2 --region $REGION --function-name $FN
  aws lambda create-function-url-config --region $REGION --function-name $FN --auth-type NONE >/dev/null
  aws lambda add-permission --region $REGION --function-name $FN --statement-id public-url \
    --action lambda:InvokeFunctionUrl --principal '*' --function-url-auth-type NONE >/dev/null
  aws lambda add-permission --region $REGION --function-name $FN --statement-id public-invoke \
    --action lambda:InvokeFunction --principal '*' >/dev/null
fi
aws lambda wait function-updated-v2 --region $REGION --function-name $FN
echo "Live at: $(aws lambda get-function-url-config --region $REGION --function-name $FN --query FunctionUrl --output text)"
