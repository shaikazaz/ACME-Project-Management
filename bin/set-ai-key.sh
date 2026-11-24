#!/usr/bin/env bash
# Script: Set the AI key of the local backend
# Purpose: Store a Google Gemini API key in the environment of the LocalStack Lambda
# Usage: ./set-ai-key.sh [--remove]

set -euo pipefail

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: $0 [--remove]"
    echo "Store (or remove) a Google Gemini API key for AI Insights, locally only"
    echo ""
    echo "The key is typed, not passed as an argument, and is kept in no file."
    echo "Run this again after LocalStack restarts or the backend is redeployed."
    exit 0
fi

# Always LocalStack, never AWS
export AWS_ENDPOINT_URL="http://localhost.localstack.cloud:4566"
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1
unset AWS_SESSION_TOKEN AWS_PROFILE

if [ "$(aws sts get-caller-identity --query Account --output text)" != "000000000000" ]; then
    echo "ERROR: This is not LocalStack. Aborting..."
    exit 1
fi

FUNCTION=$(aws lambda list-functions --output text \
    --query "Functions[?contains(FunctionName, 'project-service')].FunctionName | [0]")
if [ -z "$FUNCTION" ] || [ "$FUNCTION" = "None" ]; then
    echo "ERROR: The backend is not deployed. Run ./bin/start-dev.sh first."
    exit 1
fi

AI_KEY=""
if [ "${1:-}" != "--remove" ]; then
    read -rsp "Google Gemini API key (hidden): " AI_KEY
    echo ""
    if [ -z "$AI_KEY" ]; then
        echo "ERROR: No key entered."
        exit 1
    fi
fi

# The key must not appear in an argument, where other users could see it. It goes
# through a file that only this user can read, in memory where possible.
umask 077
if [ -d /dev/shm ]; then
    REQUEST=$(mktemp -p /dev/shm)
else
    REQUEST=$(mktemp)
fi
trap 'rm -f "$REQUEST"' EXIT

aws lambda get-function-configuration --function-name "$FUNCTION" --output json |
    AI_KEY="$AI_KEY" python3 -c '
import json, os, sys
config = json.load(sys.stdin)
variables = config["Environment"]["Variables"]
variables.pop("GEMINI_API_KEY", None)
if os.environ["AI_KEY"]:
    variables["GEMINI_API_KEY"] = os.environ["AI_KEY"]
print(json.dumps({
    "FunctionName": config["FunctionName"],
    "Environment": {"Variables": variables},
}))' > "$REQUEST"

# The result is discarded, because it would show the environment.
aws lambda update-function-configuration \
    --cli-input-json "file://$REQUEST" > /dev/null
rm -f "$REQUEST"

if [ -n "$AI_KEY" ]; then
    echo "Done. AI Insights uses the key from the next request."
else
    echo "Done. AI Insights uses fixed rules."
fi
