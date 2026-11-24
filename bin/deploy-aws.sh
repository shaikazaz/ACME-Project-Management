#!/usr/bin/env bash
# Script: AWS Deployment
# Purpose: Plan, deploy and check the application in the workshop's AWS account
# Usage: ./deploy-aws.sh [plan|apply|admin|demo-logins|demo|check]
# Default: plan

set -euo pipefail

MODE=${1:-plan}
case "$MODE" in
    plan | apply | admin | demo-logins | demo | check) ;;
    *)
        echo "Usage: $0 [plan|apply|admin|demo-logins|demo|check]"
        echo "  plan    Show what would change. Changes nothing (default)"
        echo "  apply   Plan, ask, deploy, migrate the database, upload the frontend, check"
        echo "  admin   Create an admin account. The password is typed and kept in no file"
        echo "  demo-logins  Show shared, limited demo logins on the public sign-in page"
        echo "  demo    Add fictional demo data. Only adds, and adds nothing when run again"
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

# The account may encrypt logs and change how long they are kept. Keep that.
LOG_GROUP=$(aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/$FUNCTION" \
    --query 'logGroups[0].[retentionInDays,kmsKeyId]' --output text)
read -r LOG_DAYS LOG_KEY <<< "$LOG_GROUP"
if [[ "${LOG_DAYS:-}" =~ ^[0-9]+$ ]]; then export TF_VAR_aws_logs_retention="$LOG_DAYS"; fi
if [[ "${LOG_KEY:-}" == arn:* ]]; then export TF_VAR_aws_logs_kms_key="$LOG_KEY"; fi

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
    demo-logins)
        echo "Everyone who opens the website will see these logins and can use them."
        echo "The backend stops them from deleting records or changing accounts."
        read -rp "Create them, or give them new passwords? Type yes: " ANSWER
        if [ "$ANSWER" != "yes" ]; then
            echo "Nothing was changed."
            exit 1
        fi
        LOGINS="$PROJECT_ROOT/frontend/.env.production.local"
        python3 - "$WORK" << 'PYTHON'
import json, pathlib, secrets, sys
work = pathlib.Path(sys.argv[1])
accounts = [
    {"label": label, "email": f"demo.{key}@acme.test",
     "password": f"Acme-{key}-{secrets.token_hex(4)}"}
    for key, label in (("admin", "Admin"), ("manager", "Project Manager"),
                       ("member", "Team Member"))
]
passwords = {account["email"]: account["password"] for account in accounts}
task = {"task": "set_shared_accounts", "passwords": passwords}
(work / "task.json").write_text(json.dumps(task))
(work / "logins").write_text(
    "# Shared demo logins of the live website. Not in Git.\n"
    f"VITE_DEMO_ACCOUNTS='{json.dumps(accounts)}'\n")
PYTHON
        run_task
        cp "$WORK/logins" "$LOGINS"
        "$SCRIPT_DIR/deploy-frontend.sh" aws
        check
        ;;
    demo)
        read -rp "Add the fictional demo data to the AWS database? Type yes: " ANSWER
        if [ "$ANSWER" != "yes" ]; then
            echo "Nothing was changed."
            exit 1
        fi
        echo '{"task": "add_demo_data"}' > "$WORK/task.json"
        run_task
        ;;
    check)
        check
        ;;
esac
