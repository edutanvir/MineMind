#!/usr/bin/env bash
# Deploy MineMind to Google Cloud Run. Run from the project root:  bash scripts/deploy_cloud_run.sh
# Needs: gcloud installed and logged in, a project with billing enabled, a .env with GEMINI_API_KEY and GEMINI_MODEL.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-northamerica-northeast2}"   # Toronto
SERVICE="${SERVICE:-minemind}"
SECRET="GEMINI_API_KEY"

[ -n "$PROJECT_ID" ] || { echo "No project. Run: gcloud config set project YOUR_PROJECT_ID"; exit 1; }
[ -f .env ] || { echo ".env not found. Run this from the project root."; exit 1; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || { echo "Run: gcloud auth login"; exit 1; }

get_env() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | tr -d '\r' | sed -e "s/^[\"']//" -e "s/[\"']\$//"; }
API_KEY="$(get_env GEMINI_API_KEY)"
MODEL="$(get_env GEMINI_MODEL)"
[ -n "$API_KEY" ] && [ -n "$MODEL" ] || { echo "GEMINI_API_KEY and GEMINI_MODEL must be set in .env"; exit 1; }

echo "Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE | Model: $MODEL"

echo "1/5 Enabling APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com --project "$PROJECT_ID"

echo "2/5 Storing the Gemini key in Secret Manager (never printed)..."
if gcloud secrets describe "$SECRET" --project "$PROJECT_ID" >/dev/null 2>&1; then
  printf '%s' "$API_KEY" | gcloud secrets versions add "$SECRET" --data-file=- --project "$PROJECT_ID" >/dev/null
else
  printf '%s' "$API_KEY" | gcloud secrets create "$SECRET" --data-file=- --replication-policy=automatic \
    --project "$PROJECT_ID" >/dev/null
fi

echo "3/5 Granting the default Compute service account access..."
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding "$SECRET" --member="serviceAccount:$SA" \
  --role=roles/secretmanager.secretAccessor --project "$PROJECT_ID" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
  --role=roles/run.builder --condition=None >/dev/null

echo "4/5 Building and deploying (first run takes a few minutes)..."
gcloud run deploy "$SERVICE" --source . --project "$PROJECT_ID" --region "$REGION" \
  --allow-unauthenticated --session-affinity \
  --max-instances 2 --memory 1Gi --cpu 1 --timeout 300 \
  --set-secrets "GEMINI_API_KEY=${SECRET}:latest" \
  --set-env-vars "GEMINI_MODEL=${MODEL},MINEMIND_SESSION_LIMIT=15,MINEMIND_DAILY_LIMIT=300"

echo "5/5 Done. Your URL:"
gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)'
