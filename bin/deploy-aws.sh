#!/usr/bin/env bash
# Script: AWS Deployment
# Purpose: Plan, deploy and check the application in the workshop's AWS account
# Usage: ./deploy-aws.sh [plan|apply|admin|check]
# Default: plan

set -euo pipefail

MODE=${1:-plan}
case "$MODE" in
    plan | apply | admin | check) ;;
    *)
        echo "Usage: $0 [plan|apply|admin|check]"
        echo "  plan    Show what would change. Changes nothing (default)"
        echo "  apply   Plan, ask, deploy, migrate the database, upload the frontend, check"
        echo "  admin   Create an admin account. The password is typed and kept in no file"
        echo "  check   Check the deployed application"
        exit 1
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" > /dev/null 2>&1 || exit 1; pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." > /dev/null 2>&1 || exit 1; pwd -P)"

# Never LocalStack, and no changes to this computer's SSH server
unset AWS_ENDPOINT_URL AWS_ENDPOINT_URL_S3 AWS_PROFILE
export AWS_REGION=${AWS_REGION:-us-east-1} AWS_PAGER="" WORKSHOP_SKIP_SSH=1
# Apart from .terraform, which belongs to the LocalStack environment
export TF_DATA_DIR="$PROJECT_ROOT/infra/.terraform-aws"

"$SCRIPT_DIR/setup-participant.sh" > /dev/null
chmod 600 "$PROJECT_ROOT/ENVIRONMENT.config"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/ENVIRONMENT.config"
if [ "$AWS_ACCOUNT_ID" = "000000000000" ]; then
    echo "ERROR: This is LocalStack. Aborting..."
    exit 1
fi
FUNCTION="$PROJECT_NAME-project-service-$PARTICIPANT_ID"

# Plans and requests can hold secrets
umask 077
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$PROJECT_ROOT/infra"
terraform init -reconfigure -input=false -backend-config="bucket=$AWS_S3_BUCKET" \
    -backend-config="region=$AWS_REGION" > /dev/null

# Run a task in the Lambda, which can reach the private database
run_task() {
    aws lambda invoke --function-name "$FUNCTION" --cli-binary-format raw-in-base64-out \
        --cli-read-timeout 120 --payload "file://$WORK/task.json" "$WORK/result.json" > /dev/null
    rm -f "$WORK/task.json"
    python3 - "$WORK/result.json" << 'PYTHON'
import json, sys
result = json.load(open(sys.argv[1]))
print(result.get("message", "The task failed. See the function's log."))
sys.exit(0 if result.get("ok") else 1)
PYTHON
}

check() {
    local url status path expected
    url=$(terraform output -raw website_url)
    for item in "/=200" "/api/project-service/health=200" \
        "/api/project-service/health/ready=200" "/api/project-service/projects=401" \
        "/api/project-service/missing=404"; do
        path=${item%=*}
        expected=${item##*=}
        status=$(curl -s -o /dev/null -m 60 -w '%{http_code}' "$url$path" || true)
        if [ "$status" = "$expected" ]; then
            echo "PASS $status $path"
        else
            echo "FAIL $status (expected $expected) $path"
        fi
    done
    echo "Website: $url"
}

case "$MODE" in
    plan)
        terraform plan -input=false -lock=false
        ;;
    apply)
        terraform plan -input=false -out="$WORK/tfplan"
        read -rp "Deploy exactly this plan? Type yes: " ANSWER
        if [ "$ANSWER" != "yes" ]; then
            echo "Nothing was changed."
            exit 1
        fi
        terraform apply -input=false "$WORK/tfplan"
        aws rds wait db-cluster-available --db-cluster-identifier "$PROJECT_NAME-rds-$PARTICIPANT_ID"
        aws lambda wait function-updated-v2 --function-name "$FUNCTION"
        echo '{"task": "migrate"}' > "$WORK/task.json"
        run_task
        "$SCRIPT_DIR/deploy-frontend.sh" aws
        check
        ;;
    admin)
        read -rp "Email: " EMAIL
        read -rp "Name: " NAME
        read -rsp "Password (12+ characters, hidden): " PASSWORD
        echo ""
        EMAIL="$EMAIL" NAME="$NAME" PASSWORD="$PASSWORD" python3 -c '
import json, os
print(json.dumps({"task": "create_admin", "email": os.environ["EMAIL"],
                  "name": os.environ["NAME"], "password": os.environ["PASSWORD"]}))' \
            > "$WORK/task.json"
        run_task
        ;;
    check)
        check
        ;;
esac
