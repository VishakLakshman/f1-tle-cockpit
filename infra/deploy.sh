#!/bin/bash
# deploy.sh -- Build, push, and wire up the F1 Telemetry Lambda function.
#
# Usage (run from ANY directory):
#   export UPSTASH_REDIS_URL="rediss://:password@host.upstash.io:6380"
#   export ALLOWED_ORIGINS="http://localhost:3000"
#   chmod +x infra/deploy.sh
#   ./infra/deploy.sh

set -euo pipefail

# Always resolve paths relative to this script, not the caller's cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
echo "==> Project root: ${ROOT_DIR}"

# Config
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="f1-telemetry-backend"
LAMBDA_FUNCTION="f1-telemetry-api"
LAMBDA_ROLE="f1-telemetry-lambda-role"
S3_BUCKET="f1-telemetry-cache-${AWS_ACCOUNT_ID}"
API_NAME="f1-telemetry-api-gw"
STAGE="prod"
MEMORY_MB=512
TIMEOUT_S=30

UPSTASH_REDIS_URL="${UPSTASH_REDIS_URL:-}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

if [[ -z "$UPSTASH_REDIS_URL" ]]; then
  echo "ERROR: export UPSTASH_REDIS_URL=rediss://:pw@host.upstash.io:6380 first"
  exit 1
fi

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
IMAGE_TAG="latest"

echo "==> AWS Account: ${AWS_ACCOUNT_ID} | Region: ${AWS_REGION}"

# Step 1: S3 bucket for pre-processed session JSON
echo "==> Creating S3 bucket: ${S3_BUCKET}"
if ! aws s3 ls "s3://${S3_BUCKET}" 2>/dev/null; then
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}"
  else
    aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  fi
  aws s3api put-public-access-block --bucket "${S3_BUCKET}" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
  echo "    Bucket created."
else
  echo "    Bucket already exists, skipping."
fi

# Step 2: ECR repository
echo "==> Creating ECR repository: ${ECR_REPO}"
aws ecr create-repository --repository-name "${ECR_REPO}" --region "${AWS_REGION}" 2>/dev/null || \
  echo "    Repository already exists, skipping."

# Step 3: Build and push Docker image
# Uses buildx with --provenance=false to produce a plain amd64 manifest.
# Without --provenance=false, buildx adds OCI attestation layers that Lambda
# rejects with: "image manifest media type is not supported"
echo "==> Logging in to ECR"
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Setting up docker buildx for linux/amd64"
docker buildx create --name amd64builder --use 2>/dev/null || docker buildx use amd64builder
docker buildx inspect --bootstrap > /dev/null

echo "==> Building and pushing image (linux/amd64)"
cd "${ROOT_DIR}/backend"
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --push \
  -t "${ECR_URI}:${IMAGE_TAG}" .
cd "${ROOT_DIR}"

# Step 4: IAM role
echo "==> Setting up IAM role: ${LAMBDA_ROLE}"

TRUST_POLICY='{
  "Version":"2012-10-17",
  "Statement":[{
    "Effect":"Allow",
    "Principal":{"Service":"lambda.amazonaws.com"},
    "Action":"sts:AssumeRole"
  }]
}'

ROLE_ARN=$(aws iam create-role \
  --role-name "${LAMBDA_ROLE}" \
  --assume-role-policy-document "${TRUST_POLICY}" \
  --query Role.Arn --output text 2>/dev/null) || \
  ROLE_ARN=$(aws iam get-role --role-name "${LAMBDA_ROLE}" --query Role.Arn --output text)

echo "    Role ARN: ${ROLE_ARN}"

aws iam attach-role-policy --role-name "${LAMBDA_ROLE}" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

# Use absolute path to lambda-policy.json -- never depends on caller's cwd
S3_POLICY=$(sed "s/YOUR_BUCKET_NAME/${S3_BUCKET}/g" "${SCRIPT_DIR}/lambda-policy.json")
aws iam put-role-policy --role-name "${LAMBDA_ROLE}" \
  --policy-name "F1TelemetryS3Cache" \
  --policy-document "${S3_POLICY}"

echo "    Waiting for IAM role to propagate..."
sleep 10

# Step 5: Lambda function
ENV_VARS="Variables={\
UPSTASH_REDIS_URL=${UPSTASH_REDIS_URL},\
FF1_S3_BUCKET=${S3_BUCKET},\
ALLOWED_ORIGINS=${ALLOWED_ORIGINS},\
API_ROOT_PATH=/${STAGE}\
}"

EXISTING=$(aws lambda get-function --function-name "${LAMBDA_FUNCTION}" \
  --region "${AWS_REGION}" 2>/dev/null || echo "")

if [[ -z "$EXISTING" ]]; then
  echo "==> Creating Lambda function: ${LAMBDA_FUNCTION}"
  LAMBDA_ARN=$(aws lambda create-function \
    --function-name "${LAMBDA_FUNCTION}" \
    --package-type Image \
    --code ImageUri="${ECR_URI}:${IMAGE_TAG}" \
    --role "${ROLE_ARN}" \
    --memory-size "${MEMORY_MB}" \
    --timeout "${TIMEOUT_S}" \
    --environment "${ENV_VARS}" \
    --region "${AWS_REGION}" \
    --query FunctionArn --output text)
else
  echo "==> Updating Lambda function: ${LAMBDA_FUNCTION}"
  aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION}" \
    --image-uri "${ECR_URI}:${IMAGE_TAG}" \
    --region "${AWS_REGION}" > /dev/null

  aws lambda wait function-updated \
    --function-name "${LAMBDA_FUNCTION}" --region "${AWS_REGION}"

  aws lambda update-function-configuration \
    --function-name "${LAMBDA_FUNCTION}" \
    --memory-size "${MEMORY_MB}" \
    --timeout "${TIMEOUT_S}" \
    --environment "${ENV_VARS}" \
    --region "${AWS_REGION}" > /dev/null

  LAMBDA_ARN=$(aws lambda get-function \
    --function-name "${LAMBDA_FUNCTION}" \
    --query Configuration.FunctionArn --output text)
fi

echo "    Lambda ARN: ${LAMBDA_ARN}"
aws lambda wait function-active --function-name "${LAMBDA_FUNCTION}" --region "${AWS_REGION}"

# Step 6: API Gateway HTTP API
echo "==> Setting up API Gateway HTTP API: ${API_NAME}"

API_ID=$(aws apigatewayv2 get-apis --region "${AWS_REGION}" \
  --query "Items[?Name=='${API_NAME}'].ApiId" --output text)

if [[ -z "$API_ID" ]]; then
  API_ID=$(aws apigatewayv2 create-api \
    --name "${API_NAME}" \
    --protocol-type HTTP \
    --cors-configuration \
      AllowOrigins="${ALLOWED_ORIGINS}",AllowMethods="GET,OPTIONS",AllowHeaders="Content-Type,Authorization" \
    --region "${AWS_REGION}" \
    --query ApiId --output text)
  echo "    Created API: ${API_ID}"
else
  echo "    API already exists: ${API_ID}"
fi

INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id "${API_ID}" \
  --integration-type AWS_PROXY \
  --integration-uri "${LAMBDA_ARN}" \
  --payload-format-version "2.0" \
  --region "${AWS_REGION}" \
  --query IntegrationId --output text 2>/dev/null || \
  aws apigatewayv2 get-integrations --api-id "${API_ID}" \
    --region "${AWS_REGION}" \
    --query "Items[0].IntegrationId" --output text)

aws apigatewayv2 create-route --api-id "${API_ID}" \
  --route-key "ANY /{proxy+}" \
  --target "integrations/${INTEGRATION_ID}" \
  --region "${AWS_REGION}" 2>/dev/null || echo "    Route already exists."

aws apigatewayv2 create-stage --api-id "${API_ID}" \
  --stage-name "${STAGE}" --auto-deploy \
  --region "${AWS_REGION}" 2>/dev/null || echo "    Stage already exists."

aws lambda add-permission \
  --function-name "${LAMBDA_FUNCTION}" \
  --statement-id "apigateway-invoke-$(date +%s)" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*/*/*" \
  --region "${AWS_REGION}" 2>/dev/null || echo "    Permission already exists."

API_URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE}"

echo ""
echo "Deployment complete!"
echo ""
echo "   API URL : ${API_URL}"
echo "   Health  : ${API_URL}/health"
echo "   Test    : ${API_URL}/api/qualifying/session-info?year=2025&gp=Bahrain&session=Q3"
echo ""
echo "   Set in your frontend .env.local:"
echo "   NEXT_PUBLIC_API_URL=${API_URL}"
echo ""
echo "   Remember: run the pipeline first before testing ghost endpoints."
echo "   cd pipeline && python process_season.py"