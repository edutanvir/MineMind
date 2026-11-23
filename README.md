# MineMind - Northern Ontario Mining Intelligence

A Gemini-powered data engineering and exploration app. It combines **NRCan Map 900A** mine locations with
**Statistics Canada Table 16-10-0019-01** monthly mineral production. Gemini calls allow-listed, read-only
Python tools; the tools query DuckDB. Gemini explains the evidence and is never the source of numbers.

> Independent prototype - not a government product.

## Features
- **Overview / Mine Explorer** - interactive Folium map with filters by province, city, commodity and feature type.
- **Production Analytics** - one exact Statistics Canada series at a time (commodity, unit, vector ID). Series are never added together.
- **Ask MineMind** - natural-language questions answered through Gemini function calling, with a "Tools used" and "Sources used" panel.
- **Data & Methods** - sources, licences, pipeline log, coverage, units and limitations.

## Architecture
```
NRCan 900A (FGDB) --+                                   +--> Streamlit pages (Folium, Plotly)
                    +--> Bronze --> Silver --> Gold --> DuckDB --+
Statistics Canada --+    raw+checksum  cleaned  Parquet   views    +--> Gemini tools (read-only, parameterized)
```
The two datasets are shown side by side but are **not joined at mine level**: provincial values are never attributed to a mine.

## Run locally
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then add your own GEMINI_API_KEY and GEMINI_MODEL
python -m src.pipeline        # optional: rebuild Bronze -> Silver -> Gold (needs the raw files in data/raw/)
streamlit run app.py
pytest
```
The Gold Parquet files in `data/processed/gold/` are committed so the app runs without the raw downloads.

## Data sources and attribution
- Natural Resources Canada, Map 900A - [Open Government Licence - Canada](https://open.canada.ca/en/open-government-licence-canada/).
- Statistics Canada, Table 16-10-0019-01 - [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence). This is not the official version of the data.

## Responsible AI
- Only three allow-listed tools; SQL text is fixed and only values are parameters; row limits are capped.
- Counts, totals, averages and tonne conversions are computed in Python and returned to Gemini.
- Missing (`..`) and suppressed (`x`) values are never treated as zero.
- No claims about pollution, health risk or mine safety. Per-session and per-day question limits protect the API quota.

## Deploy to Google Cloud Run (Toronto)
1. Create a Google Cloud project, link a billing account and set a budget alert.
2. `gcloud auth login` then `gcloud config set project YOUR_PROJECT_ID`
3. `bash scripts/deploy_cloud_run.sh`

The script enables the APIs, stores the Gemini key in Secret Manager, deploys from the `Dockerfile`, and prints the URL.
The key is never baked into the image. To delete everything afterwards: `gcloud run services delete minemind --region northamerica-northeast2`.

## Project layout
`app.py`, `pages/` (Streamlit) - `src/ingestion`, `src/transformation`, `src/database`, `src/analytics`, `src/ai`, `src/ui` - `scripts/` (Docker DB build, deploy) - `tests/`

## Known limitations
Map 900A shows significant mapped features only. Statistics Canada values are provincial and may be revised. The commodity shown on the map is the first one listed in the source record.
