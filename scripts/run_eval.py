"""Run MineMind's golden questions through Gemini and score tool choice, arguments and honesty.

    python scripts/run_eval.py --dry-run          # validate the question file only, no API calls
    python scripts/run_eval.py                    # live run (needs GEMINI_API_KEY in .env)
    python scripts/run_eval.py --only g01 g04     # run a subset
    python scripts/run_eval.py --sleep 10         # slower pacing for the free tier

Writes evals/results/latest.md (commit it) and latest.json (git-ignored).

Which system prompt is used: SYSTEM_PROMPT from src/ai/gemini_agent.py if that module defines one,
otherwise the built-in FALLBACK_PROMPT below. The script prints which one it used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # tools.py opens data/minemind.duckdb relative to the repo root

QUESTIONS = ROOT / "evals" / "golden_questions.json"
RESULTS = ROOT / "evals" / "results"
KNOWN_TOOLS = {"get_production_trend", "search_mines", "mines_near_place"}

FALLBACK_PROMPT = (
    "You are MineMind, an assistant for Northern Ontario mining data. "
    "Answer only from the tools provided; they query Statistics Canada Table 16-10-0019-01 and NRCan Map 900A. "
    "Never do arithmetic yourself: use the numbers the tools return. "
    "Never add concentrates, recoverable and refined series together. "
    "Treat '..' and 'x' as missing, not zero. "
    "State caveats: production data is provincial, not mine-level; Map 900A is not a complete list of mines. "
    "You cannot modify data. If the tools cannot answer, say so plainly."
)


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_questions(only: list[str] | None) -> list[dict]:
    data = json.loads(QUESTIONS.read_text())["questions"]
    return [q for q in data if not only or q["id"] in only]


def validate(questions: list[dict]) -> list[str]:
    problems = []
    for q in questions:
        for key in ("id", "category", "question", "expect"):
            if key not in q:
                problems.append(f"{q.get('id', '?')}: missing '{key}'")
        for t in q.get("expect", {}).get("tools_any", []):
            if t not in KNOWN_TOOLS:
                problems.append(f"{q['id']}: unknown tool '{t}'")
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        problems.append("duplicate question ids")
    return problems


def system_prompt() -> tuple[str, str]:
    try:
        from src.ai import gemini_agent  # type: ignore

        for name in ("SYSTEM_PROMPT", "SYSTEM_INSTRUCTION"):
            val = getattr(gemini_agent, name, None)
            if isinstance(val, str) and val.strip():
                return val, f"src.ai.gemini_agent.{name}"
    except Exception:
        pass
    return FALLBACK_PROMPT, "built-in FALLBACK_PROMPT"


def ask(client, types, model_list: list[str], prompt: str, question: str, log: list):
    from src.ai.tools import tool_set

    last: Exception | None = None
    for model in model_list:
        for attempt in range(4):
            try:
                del log[:]
                resp = client.models.generate_content(
                    model=model,
                    contents=question,
                    config=types.GenerateContentConfig(system_instruction=prompt, tools=tool_set(log), temperature=0),
                )
                return (resp.text or "").strip(), model
            except Exception as exc:  # retry only transient errors
                msg = str(exc)
                if not any(code in msg for code in ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                    raise
                last = exc
                time.sleep(min(3 * 2 ** attempt, 30))
    raise RuntimeError(f"all models failed: {last}")


def score(q: dict, answer: str, log: list[dict]) -> dict[str, bool]:
    exp = q["expect"]
    called = [c["tool"] for c in log]
    low = answer.lower()
    checks: dict[str, bool] = {}
    if exp.get("tools_any"):
        checks["tool choice"] = any(t in exp["tools_any"] for t in called)
    for arg, needle in (exp.get("args_contain") or {}).items():
        checks[f"arg {arg}"] = any(str(needle).lower() in str(c.get("args", {}).get(arg, "")).lower() for c in log)
    if exp.get("answer_any"):
        checks["answer mentions"] = any(s.lower() in low for s in exp["answer_any"])
    if exp.get("answer_none"):
        checks["answer avoids"] = not any(s.lower() in low for s in exp["answer_none"])
    return checks


def write_report(rows: list[dict], model_used: str, prompt_src: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    passed = sum(r["passed"] for r in rows)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# MineMind eval results", "",
        f"- Run: {stamp}", f"- Model: `{model_used}`", f"- System prompt: {prompt_src}",
        f"- **Passed {passed} of {len(rows)}**", "",
        "| ID | Category | Result | Tools called | Failed checks |", "|---|---|---|---|---|",
    ]
    for r in rows:
        failed = ", ".join(k for k, v in r["checks"].items() if not v) or "-"
        tools = ", ".join(r["tools"]) or "none"
        lines.append(f"| {r['id']} | {r['category']} | {'PASS' if r['passed'] else 'FAIL'} | {tools} | {failed} |")
    lines += ["", "Checks are keyword and tool-name heuristics: a smoke test, not proof of correctness.", ""]
    (RESULTS / "latest.md").write_text("\n".join(lines))
    (RESULTS / "latest.json").write_text(json.dumps(rows, indent=2, default=str))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sleep", type=float, default=6.0, help="seconds between questions (free-tier pacing)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any question fails")
    args = ap.parse_args()

    questions = load_questions(args.only)
    problems = validate(questions)
    if problems:
        print("Question file problems:\n  " + "\n  ".join(problems))
        return 1
    if args.dry_run:
        print(f"OK: {len(questions)} questions valid. Tools known: {', '.join(sorted(KNOWN_TOOLS))}")
        for q in questions:
            print(f"  {q['id']}  [{q['category']}]  {q['question']}")
        return 0

    load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY is not set. Put it in .env or the environment.")
        return 1
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    primary = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    fallbacks = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
    prompt, prompt_src = system_prompt()
    print(f"Model: {primary}  |  system prompt: {prompt_src}")

    rows, used = [], primary
    log: list[dict] = []
    for i, q in enumerate(questions):
        try:
            answer, used = ask(client, types, [primary] + fallbacks, prompt, q["question"], log)
            checks = score(q, answer, log)
            err = None
        except Exception as exc:
            answer, checks, err = "", {"ran": False}, str(exc)
        passed = bool(checks) and all(checks.values())
        rows.append({"id": q["id"], "category": q["category"], "question": q["question"], "answer": answer,
                     "tools": [c["tool"] for c in log], "checks": checks, "passed": passed, "error": err})
        print(f"{'PASS' if passed else 'FAIL'}  {q['id']}  {q['category']:<22}  tools={[c['tool'] for c in log]}")
        if i < len(questions) - 1:
            time.sleep(args.sleep)

    write_report(rows, used, prompt_src)
    passed = sum(r["passed"] for r in rows)
    print(f"\nPassed {passed} of {len(rows)}. Report: evals/results/latest.md")
    return 1 if (args.strict and passed < len(rows)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
