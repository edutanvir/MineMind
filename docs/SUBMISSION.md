# Submission form: paste-ready answers

Deadline per the event text: **end of day Friday Nov 27**. The form itself closes **Saturday Nov 28, 3:30 PM EST**. Submit Friday so Saturday is for the booth.

## Project name
MineMind

## One-liner
Ask Northern Ontario's mining data anything: Gemini chooses verified, read-only queries over a Bronze–Silver–Gold lakehouse, so every number is traceable to government data.

## Source code (GitHub)
https://github.com/edutanvir/MineMind  <!-- EDIT if the repo name differs -->

## Description (Markdown)

**MineMind** turns two public Canadian datasets (Statistics Canada monthly mineral production and NRCan Map 900A mine features) into a Gemini-powered explorer for Northern Ontario.

### How Gemini is used
Gemini is the reasoning core. It receives the user's question and the schemas of three Python tools, **chooses a tool and its arguments with function calling**, reads the structured result and writes the answer. The tools are read-only and parameterized, results are bounded, and **all totals and unit conversions are computed in Python, so the model never does arithmetic**. Every result carries its source, licence and caveat, and a tool trace under each answer shows exactly what was run.

### Data and pipeline
Python ingestion → **Bronze → Silver → Gold** lakehouse (Parquet) → **DuckDB**. Runs are logged in `etl_run_log`; `source_manifest` records provenance.

### Honest by design
Production data is provincial, not mine-level; Map 900A is not a complete list of mines; suppressed or unavailable months are never treated as zero; concentrates, recoverable and refined series are never added together. MineMind says so instead of guessing.

### Built with
Gemini API (free tier), Gemini CLI + agents + skills, Google Antigravity, Databricks (Apps + Secret Scope, used instead of Firebase and Google Cloud), Python, Streamlit, DuckDB, pytest.

### Quality
A pytest suite covers the tool guardrails offline, and a golden-question script scores Gemini's tool choice, arguments and refusals.

## Technologies
Gemini API · Gemini CLI · Google Antigravity · Databricks Apps · Databricks Secret Scope · Python · Streamlit · DuckDB · Parquet · pandas · GeoPandas · pytest · GitHub

## AI the project calls
Gemini API (model set by `GEMINI_MODEL`, currently `gemini-3.5-flash-lite`) via function calling with three read-only tools.

## Live demo link
<!-- EDIT: public mirror URL. Databricks Apps cannot be opened without a Databricks login. -->

## Other links
- Demo video: <!-- EDIT -->
- Animated architecture: https://edutanvir.github.io/MineMind/ <!-- after enabling GitHub Pages: Settings → Pages → main /docs -->

## Prize categories
Tick **Best Use of the Google Gemini API**. Tick the Antigravity coding-tool box only if you are comfortable describing how you used it (see `docs/AI_TOOLING.md`).

## Before you press submit
- [ ] Repo is public and the README renders (banner, diagram, Mermaid chart)
- [ ] `git log` shows commits starting after the Nov 21 kick-off
- [ ] `.env` is not in the repo or its history (`git log --all -- .env` is empty)
- [ ] `pytest -q` passes
- [ ] Demo video link opens in a private window
- [ ] Live demo link (if any) opens without a login
