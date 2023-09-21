#!/bin/bash
set -eo pipefail

FUNCTION_NAME=${FUNCTION_NAME:-python-atlas-test}
AWS_REGION=${AWS_REGION:-us-east-1}

if [ -z "$MONGODB_URI" ]
then
    echo "missing required \$MONGODB_URI env var required!"
    exit 1
fi

sam build

echo "Deploying Lambda function..."
sam deploy \
  --stack-name "${FUNCTION_NAME}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides "MongoDbUri=${MONGODB_URI}" \
  --region "${AWS_REGION}"

sam delete --stack-name ${FUNCTION_NAME} --no-prompts --region "${AWS_REGION}"