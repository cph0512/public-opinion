#!/usr/bin/env bash
# 部署 FastAPI 版輿情搜尋到 Google Cloud Run。
# 使用前:
#   1. gcloud auth login
#   2. 設定 gcloud config set project <PROJECT_ID>
#   3. bash deploy_cloudrun.sh
#
# 需要的 API(第一次會自動被 gcloud 提示啟用):
#   - Cloud Run Admin API
#   - Cloud Build API
#   - Artifact Registry API

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
SERVICE_NAME="${SERVICE_NAME:-public-opinion}"
REGION="${REGION:-asia-east1}"

if [[ -z "${PROJECT_ID}" ]]; then
    echo "❌ 沒有設定 GCP project。請跑:gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo "🚀 部署到 Cloud Run"
echo "  Project : ${PROJECT_ID}"
echo "  Service : ${SERVICE_NAME}"
echo "  Region  : ${REGION}"
echo ""

# 收集要傳給 Cloud Run 的環境變數(只帶有值的)
ENV_VARS=""
for KEY in ANTHROPIC_API_KEY REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET \
           THREADS_ACCESS_TOKEN FACEBOOK_ACCESS_TOKEN; do
    VAL="${!KEY:-}"
    if [[ -n "${VAL}" ]]; then
        ENV_VARS+="${KEY}=${VAL},"
    fi
done
ENV_VARS="${ENV_VARS%,}"

EXTRA_ARGS=()
if [[ -n "${ENV_VARS}" ]]; then
    EXTRA_ARGS+=(--set-env-vars "${ENV_VARS}")
fi

gcloud run deploy "${SERVICE_NAME}" \
    --source . \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated \
    --port 8080 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --min-instances 0 \
    --max-instances 3 \
    "${EXTRA_ARGS[@]}"

echo ""
echo "✅ 完成。用下列指令查看網址:"
echo "   gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'"
