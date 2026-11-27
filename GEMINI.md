# MineMind: context for Gemini CLI

MineMind answers questions about Northern Ontario mining using two public Canadian datasets.
Gemini calls three read-only Python tools over a DuckDB database; it never writes data and never does arithmetic.

## Architecture in one breath
Statistics Canada Table 16-10-0019-01 + NRCan Map 900A -> Python ingestion -> Bronze (data/raw) -> Silver -> Gold (data/processed/gold) -> DuckDB (data/minemind.duckdb) -> Python tools (src/ai/tools.py) -> Gemini API function calling -> Streamlit (app.py, pages/).
Deployed from GitHub to Databricks Apps; GEMINI_API_KEY lives in a Databricks Secret Scope.

## Commands
- Run the app: `streamlit run app.py`
- Rebuild data: `python -m src.pipeline` then `python scripts/build_db.py`
- Tests: `pytest -q`
- Offline eval check: `python scripts/run_eval.py --dry-run`

## Rules for any change (keep these true)
1. Tools in `src/ai/tools.py` are read-only: DuckDB `read_only=True`, parameterized SQL, no string-built values.
2. Never let the model do arithmetic. Compute totals, averages and unit conversions in Python and return them as fields.
3. Every tool result carries `source` (dataset, licence, caveat). Keep it.
4. Concentrates, recoverable and refined are different series. Never add them together.
5. `..` (not available) and `x` (suppressed) are missing, never zero.
6. StatCan data is provincial, not mine-level. NRCan Map 900A is significant mapped features, not every mine. Do not imply otherwise.
7. Secrets only through environment variables. Never print or commit `GEMINI_API_KEY`.
8. Add or change a tool together with a test in `tests/` and a case in `evals/golden_questions.json`.

## Where things are
- `src/ai/tools.py` tool functions; `src/ai/gemini_agent.py` agent loop; `src/ai/guard.py` guardrails
- `src/ui/trace_panel.py` shows the tool trace under each answer
- `.agents/skills/` reusable skills: `data-quality-check`, `add-ai-tool`
- `docs/AI_TOOLING.md` how the Gemini tooling was used
