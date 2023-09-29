#!/bin/bash
set -eo pipefail

STACK_NAME=${STACK_NAME:-python-atlas-test}
AWS_REGION=${AWS_REGION:-us-east-1}

sam delete --stack-name "${STACK_NAME}" --no-prompts --region "${AWS_REGION}"
