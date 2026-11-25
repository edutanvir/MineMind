#!/usr/bin/env bash
# Deploy MineMind to Google Cloud Run. Run from the project root:  bash scripts/deploy_cloud_run.sh
#
# Core deploy (do this first):   bash scripts/deploy_cloud_run.sh
# With optional Google sign-in + saved questions (Firestore), only after the core deploy works:
#                                ENABLE_ACCOUNTS=1 bash scripts/deploy_cloud_run.sh
#
# Needs: gcloud installed and logged in, a project with billing enabled, and a .env with
# GEMINI_API_KEY and GEMINI_MODEL (optional: GEMINI_FALLBACK_MODEL, one model ID, no commas).
# Every run re-applies ALL secrets and env vars, so this script is the single source of truth.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-northamerica-northeast2}"          # Toronto
SERVICE="${SERVICE:-minemind}"
SECRET="GEMINI_API_KEY"
ENABLE_ACCOUNTS="${ENABLE_ACCOUNTS:-0}"
AUTH_SECRET="minemind-auth"
AUTH_FILE="${AUTH_FILE:-.streamlit/secrets.cloud.toml}"
AUTH_MOUNT="/home/appuser/.streamlit/secrets.toml"   # Streamlit reads ~/.streamlit/secrets.toml
FIRESTORE_LOCATION="${FIRESTORE_LOCATION:-$REGION}"  # permanent once the database is created

[ -n "$PROJECT_ID" ] || { echo "No project. Run: gcloud config set project YOUR_PROJECT_ID"; exit 1; }
[ -f .env ] || { echo ".env not found. Run this from the project root."; exit 1; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || { echo "Run: gcloud auth login"; exit 1; }

get_env() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | tr -d '\r' | sed -e "s/^[\"']//" -e "s/[\"']\$//" || true; }
API_KEY="$(get_env GEMINI_API_KEY)"
MODEL="$(get_env GEMINI_MODEL)"
FALLBACK="$(get_env GEMINI_FALLBACK_MODEL)"
[ -n "$API_KEY" ] && [ -n "$MODEL" ] || { echo "GEMINI_API_KEY and GEMINI_MODEL must be set in .env"; exit 1; }
case "$MODEL$FALLBACK" in *,*) echo "GEMINI_MODEL / GEMINI_FALLBACK_MODEL must each be a single model ID (no commas)."; exit 1;; esac

# Check the optional-accounts inputs BEFORE changing anything in the cloud.
if [ "$ENABLE_ACCOUNTS" = "1" ]; then
  [ -f "$AUTH_FILE" ] || { echo "$AUTH_FILE not found. Copy .streamlit/secrets.toml.example to $AUTH_FILE and fill it in."; exit 1; }
  grep -q '^\[auth\]' "$AUTH_FILE" || { echo "$AUTH_FILE must contain an [auth] section."; exit 1; }
  for key in redirect_uri cookie_secret client_id client_secret server_metadata_url; do
    grep -Eq "^[[:space:]]*${key}[[:space:]]*=" "$AUTH_FILE" || { echo "$AUTH_FILE is missing '$key'."; exit 1; }
  done
  if grep -Eqi 'YOUR_|CHANGE_ME' "$AUTH_FILE"; then echo "$AUTH_FILE still contains placeholder values."; exit 1; fi
  REDIRECT="$(grep -E '^[[:space:]]*redirect_uri' "$AUTH_FILE" | head -n1 | cut -d= -f2- | tr -d " \"'\r")"
  case "$REDIRECT" in https://*/oauth2callback) ;; *) echo "redirect_uri in $AUTH_FILE must be https://<your-cloud-run-url>/oauth2callback (got: $REDIRECT)"; exit 1;; esac
fi

echo "Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE | Model: $MODEL | Fallback: ${FALLBACK:-none} | Accounts: $ENABLE_ACCOUNTS"

echo "[1] Enabling APIs..."
APIS="run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com"
[ "$ENABLE_ACCOUNTS" = "1" ] && APIS="$APIS firestore.googleapis.com"
# shellcheck disable=SC2086
gcloud services enable $APIS --project "$PROJECT_ID"

echo "[2] Storing the Gemini key in Secret Manager (never printed)..."
if gcloud secrets describe "$SECRET" --project "$PROJECT_ID" >/dev/null 2>&1; then
  printf '%s' "$API_KEY" | gcloud secrets versions add "$SECRET" --data-file=- --project "$PROJECT_ID" >/dev/null
else
  printf '%s' "$API_KEY" | gcloud secrets create "$SECRET" --data-file=- --replication-policy=automatic \
    --project "$PROJECT_ID" >/dev/null
fi

echo "[3] Granting the default Compute service account access..."
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding "$SECRET" --member="serviceAccount:$SA" \
  --role=roles/secretmanager.secretAccessor --project "$PROJECT_ID" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
  --role=roles/run.builder --condition=None >/dev/null

ENV_VARS="GEMINI_MODEL=${MODEL},MINEMIND_SESSION_LIMIT=15,MINEMIND_DAILY_LIMIT=300"
[ -n "$FALLBACK" ] && ENV_VARS="${ENV_VARS},GEMINI_FALLBACK_MODEL=${FALLBACK}"
SECRETS="GEMINI_API_KEY=${SECRET}:latest"   # --set-secrets replaces the whole list, so build it in one place

if [ "$ENABLE_ACCOUNTS" = "1" ]; then
  echo "[3b] Optional accounts: Firestore database, permissions and auth secret..."
  if ! gcloud firestore databases describe --database="(default)" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud firestore databases create --database="(default)" --location="$FIRESTORE_LOCATION" \
      --type=firestore-native --project "$PROJECT_ID"
  fi
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role=roles/datastore.user --condition=None >/dev/null
  if gcloud secrets describe "$AUTH_SECRET" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets versions add "$AUTH_SECRET" --data-file="$AUTH_FILE" --project "$PROJECT_ID" >/dev/null
  else
    gcloud secrets create "$AUTH_SECRET" --data-file="$AUTH_FILE" --replication-policy=automatic \
      --project "$PROJECT_ID" >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$AUTH_SECRET" --member="serviceAccount:$SA" \
    --role=roles/secretmanager.secretAccessor --project "$PROJECT_ID" >/dev/null
  SECRETS="${SECRETS},${AUTH_MOUNT}=${AUTH_SECRET}:latest"
  ENV_VARS="${ENV_VARS},MINEMIND_ENABLE_ACCOUNTS=1,GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
fi

echo "[4] Building and deploying (first run takes a few minutes)..."
gcloud run deploy "$SERVICE" --source . --project "$PROJECT_ID" --region "$REGION" \
  --allow-unauthenticated --session-affinity \
  --max-instances 2 --memory 1Gi --cpu 1 --timeout 300 \
  --set-secrets "$SECRETS" \
  --set-env-vars "$ENV_VARS"

echo "[5] Done. Your URL:"
URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
echo "$URL"
if [ "$ENABLE_ACCOUNTS" = "1" ]; then
  echo "Sign-in only works if this exact redirect URI is registered in your Google OAuth client:"
  echo "  ${URL}/oauth2callback"
fi
