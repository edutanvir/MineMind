# Built with the Gemini tooling

MineMind uses the Gemini stack in two ways: **inside the product** (the Gemini API answers questions) and **around the product** (Gemini CLI, agents, skills and Antigravity helped build it).

## 1. Gemini API (free tier): inside the product

- Gemini receives the user's question and the schemas of three Python tools in `src/ai/tools.py`.
- It chooses a tool and its arguments (function calling), reads the structured result, and writes the answer.
- The model is set with `GEMINI_MODEL` in `.env`; the key comes from `GEMINI_API_KEY` (a Databricks Secret Scope in production).
- Guardrails and the full tool list are described in the [README](../README.md#how-gemini-is-used).

## 2. Gemini CLI + agents + skills: around the product

| File | What it does |
|---|---|
| [`GEMINI.md`](../GEMINI.md) | Project context Gemini CLI loads at the start of every session: architecture, commands and the rules that must stay true |
| [`.gemini/settings.json`](../.gemini/settings.json) | Tells Gemini CLI to use `GEMINI.md` as the context file |
| [`.agents/skills/data-quality-check/`](../.agents/skills/data-quality-check/SKILL.md) | Skill: validate Silver and Gold after a pipeline run |
| [`.agents/skills/add-ai-tool/`](../.agents/skills/add-ai-tool/SKILL.md) | Skill: add a new read-only Gemini tool the way `tools.py` does |

`.agents/skills/` is discovered by both Gemini CLI and Antigravity, so one set of skills serves both.

**See it working**

```bash
gemini            # start Gemini CLI in the repo root
/memory show      # shows the loaded GEMINI.md context
/skills list      # lists data-quality-check and add-ai-tool
```

<!-- EDIT: add 2-3 sentences in your own words about what you actually delegated to Gemini CLI and agents
     (for example: pipeline refactor, test writing, README review). Keep only things you really did. -->

## 3. Google Antigravity: around the product

- Antigravity was used early in the build, until the free credit ran out; development then continued in VS Code.
- The workspace rule [`.agents/rules/minemind-guardrails.md`](../.agents/rules/minemind-guardrails.md) keeps the agent inside the project's guardrails (read-only tools, no model arithmetic, no secrets in code).

<!-- EDIT: say what Antigravity produced (for example the first pipeline scaffold, the Streamlit page skeleton). -->

## 4. Databricks instead of Firebase and Google Cloud

| Need | Used here | Instead of |
|---|---|---|
| Hosting the Streamlit app | Databricks Apps, deployed from GitHub | Firebase Hosting / Cloud Run |
| Holding `GEMINI_API_KEY` | Databricks Secret Scope | Secret Manager |
| Data serving | DuckDB over Gold Parquet | BigQuery / Cloud SQL |

Deploy steps: [`DEPLOY_DATABRICKS.md`](DEPLOY_DATABRICKS.md).

## Evidence checklist for judges

- [ ] `GEMINI.md` and `.agents/skills/` are in the repo
- [ ] A screenshot of `/skills list` in Gemini CLI at `docs/assets/screenshots/gemini-cli-skills.png`
- [ ] A screenshot of Antigravity with the MineMind workspace open at `docs/assets/screenshots/antigravity-workspace.png`
- [ ] The Ask MineMind page with its tool trace expanded at `docs/assets/screenshots/tool-trace.png`
