# Demo script: video (90 seconds) and booth

## Pitch line
"Gemini decides which verified query to run. The numbers always come from DuckDB over our Gold layer, never from the model."

## 90-second video shot list

| Time | On screen | Say |
|---|---|---|
| 0:00 | Banner / title | "Northern Ontario mining data is public but scattered. MineMind lets you just ask." |
| 0:08 | Architecture diagram (animated page) | "Two government datasets flow through Bronze, Silver and Gold into DuckDB. Gemini sits on top and can only call three read-only tools." |
| 0:25 | Ontario Mine Explorer | "NRCan mine features on a map." |
| 0:33 | Ask MineMind: **Which mines are within 40 km of Sudbury?** | "Gemini picks the radius-search tool." Expand the **tool trace**. |
| 0:50 | Ask: **How much nickel did Ontario produce in the most recent months?** | "Totals and tonne conversions are computed in Python, not by the model." |
| 1:05 | Ask: **Add together Ontario's nickel concentrates and refined nickel.** | "It refuses: those are different series. Guardrails live in the tools." |
| 1:15 | Ask: **Which individual mine produced the most nickel last year?** | "And it tells you the data is provincial, not mine-level." |
| 1:25 | README / Databricks | "Built with Gemini API, Gemini CLI and Antigravity, deployed on Databricks instead of Firebase and Google Cloud." |

Record at 1080p, one take per question, keep the tool trace open for the first one.

## Booth (60 seconds)
1. Problem: public mining data, no easy way to ask questions of it.
2. Show the animated diagram on screen as the backdrop.
3. Let a visitor type a question; expand the tool trace.
4. Close with the honest-limits question (mine-level production) to show it does not guess.

**Fallbacks:** keep the demo video on the desktop; keep the three demo questions in a text file; keep a screenshot of the tool trace. If Gemini is rate-limited on the free tier, switch to the video and the screenshots.

## Questions judges may ask

**Why function calling instead of RAG?**
The data is structured and numeric. Function calling lets Gemini choose a precise query and return exact values; retrieval over text would risk paraphrased or invented numbers.

**How do you stop hallucinated numbers?**
The model never computes. Tools return numbers and ready-made summaries, and the answer is written from those. The tool trace shows every call.

**What stops a destructive or injected query?**
There is no write tool, DuckDB is opened read-only, SQL is parameterized, and limits are clamped. The test suite includes an injection string and a read-only check.

**Why Databricks instead of Firebase or Google Cloud?**
It is where our data-engineering workflow lives: the Gemini key sits in a Secret Scope and the Streamlit app deploys from GitHub to Databricks Apps. Gemini is still the core of the product.

**What did Gemini CLI and Antigravity do?**
See `docs/AI_TOOLING.md`. Gemini CLI reads `GEMINI.md` and two project skills; Antigravity was used early in the build.

**What is the limitation?**
Statistics Canada production is provincial, and Map 900A lists significant mapped features only. Linking production to individual mines needs another source. MineMind says this in its answers.

**What next?**
More place anchors, a data-freshness indicator, and a bigger golden-question set with results tracked over time.
