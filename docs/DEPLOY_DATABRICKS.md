# Deploy MineMind on Databricks Apps

GitHub → **Databricks Apps** (hosts Streamlit) with `GEMINI_API_KEY` in a **Databricks Secret Scope**.

## 1. Store the Gemini key in a Secret Scope

```bash
databricks secrets create-scope minemind
databricks secrets put-secret minemind gemini_api_key      # paste the key when prompted
```

Use a dedicated scope for this app so the app can read only what it needs.

## 2. Create the app from the GitHub repo

Create the app in the Databricks workspace (Compute → Apps) and point it at the repository, or sync the repo to a workspace Git folder and deploy from there.

## 3. Add the secret as an app resource

App settings → **Resources** → **+ Add resource** → **Secret**. Choose the scope and key above and give the resource a key, for example `gemini_api_key`.

## 4. Expose it to the code in `app.yaml`

Reference the resource with `valueFrom`; never put the key in `value`:

```yaml
env:
  - name: GEMINI_API_KEY
    valueFrom: gemini_api_key        # the resource key from step 3
  - name: GEMINI_MODEL
    value: gemini-3.5-flash-lite     # not sensitive, safe to hardcode
```

Keep the existing `command` that starts Streamlit. In Python the key is read as `os.environ["GEMINI_API_KEY"]`.

## 5. Deploy and test

Deploy, open the app URL while signed in to Databricks, ask one question on **Ask MineMind** and expand the tool trace.

## Who can open the app

Databricks Apps are only reachable by signed-in Databricks users; a public link is not possible. For judges and the public:

1. **Demo video** in the submission form.
2. **Run locally**: the [Quick start](../README.md#quick-start) works from a fresh clone.
3. **Public mirror** (optional, 15 minutes): deploy the same repo on [Streamlit Community Cloud](https://share.streamlit.io):
   - New app → this repo, branch `main`, main file `app.py`.
   - Advanced settings → Secrets: `GEMINI_API_KEY = "..."` and `GEMINI_MODEL = "gemini-3.5-flash-lite"`.
   - Use a **separate API key** for the mirror, because anyone with the link can trigger calls on the free-tier quota.
   - `data/minemind.duckdb` must be in the repo (or built on startup).

Then put the public URL in the README's commented link row and in the submission form's live demo field.
