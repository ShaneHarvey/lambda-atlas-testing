#!/bin/bash
set -eo pipefail

STACK_NAME=${STACK_NAME:-python-atlas-test}
AWS_REGION=${AWS_REGION:-us-east-1}

if [ -z "$MONGODB_URI" ]
then
    echo "missing required \$MONGODB_URI env var required!"
    exit 1
fi

sam build

echo "Deploying Lambda function..."
sam deploy \
  --stack-name "${STACK_NAME}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides "MongoDbUri=${MONGODB_URI}" \
  --region "${AWS_REGION}"

#echo "Getting Lambda function URL..."
LAMBDA_FUNCTION_ARN=$(sam list stack-outputs \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --output json | jq '.[] | select(.OutputKey == "MongoDBFunction") | .OutputValue' | tr -d '"'
)
echo "Lambda function ARN: $LAMBDA_FUNCTION_ARN"
export LAMBDA_FUNCTION_ARN=$LAMBDA_FUNCTION_ARN

echo "Getting Lambda function URL..."
LAMBDA_FUNCTION_URL=$(aws lambda get-function-url-config \
   --function-name "${LAMBDA_FUNCTION_ARN}" \
   --region "${AWS_REGION}" \
   --output json | jq '.FunctionUrl' | tr -d '"'
)
echo "Lambda function URL: $LAMBDA_FUNCTION_URL"
export LAMBDA_FUNCTION_URL=$LAMBDA_FUNCTION_URL

check_lambda_output () {
  if grep -q FunctionError output.json
  then
      echo "Exiting due to FunctionError!"
      exit 1
  fi
  cat output.json | jq -r '.LogResult' | base64 --decode
}

aws lambda invoke --function-name "${LAMBDA_FUNCTION_ARN}" --region "${AWS_REGION}" --log-type Tail lambda-invoke-standard.json > output.json
check_lambda_output

if [ ! -d .venv ]
then
    python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install pymongo
python loadtest.py
