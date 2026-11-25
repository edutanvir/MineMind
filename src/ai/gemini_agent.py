"""src/ai/gemini_agent.py - sends a question to Gemini, which may call the tools."""
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src.ai import tools

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# Optional backup model(s), separated by ';'. Used only when the main model keeps failing with a busy error.
FALLBACK_MODELS = [m.strip() for m in re.split(r"[;,]", os.getenv("GEMINI_FALLBACK_MODEL", "")) if m.strip()]
RETRY_CODES = {429, 500, 503, 504}
RETRY_DELAYS = (1, 3)  # seconds between attempts, so 3 attempts per model

SYSTEM = (
    "You are MineMind, an evidence-first mining data assistant. "
    "Use the supplied tools for every count, name and number; never do arithmetic yourself. "
    "For totals, averages, latest values and tonne conversions use the fields in series_summary; "
    "if a figure is not provided, say you cannot compute it. "
    "Never invent mine names, production values, dates or units. "
    "Statistics Canada observations are provincial, not mine-level; never attribute them to a mine. "
    "One commodity can have several series (concentrates, recoverable, refined). "
    "Report each series separately with its label and unit and never add them. "
    "If a tool returns total_matches or total_within_radius larger than the rows shown, say so. "
    "If a tool returns valid_* lists, retry once with a valid value. "
    "If a value is missing or suppressed, say so; never treat it as zero. "
    "Do not infer pollution, health risk or mine safety. "
    "Always state the unit with production numbers. "
    "Finish with one line naming the datasets used."
)

_client = None


def _get_client():
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("Gemini API key is missing.")

        _client = genai.Client(api_key=api_key)

    return _client


def ask(question: str) -> dict:
    """Return {"answer", "tool_calls", "ok", "model"}. The tool log is private to this call."""
    log: list[dict] = []
    code = None
    for model in [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]:
        for attempt in range(len(RETRY_DELAYS) + 1):
            log.clear()
            try:
                response = _get_client().models.generate_content(
                    model=model,
                    contents=question,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM,
                        tools=tools.tool_set(log),
                    ),
                )
                answer = response.text or "Gemini returned no text. Try rephrasing the question."
                return {"answer": answer, "tool_calls": log, "ok": True, "model": model}
            except errors.APIError as e:
                code = getattr(e, "code", None)
                if code not in RETRY_CODES:
                    return {"answer": f"Gemini API error ({code}). Please try again.",
                            "tool_calls": [], "ok": False, "model": model}
                if attempt < len(RETRY_DELAYS):
                    time.sleep(RETRY_DELAYS[attempt])
            except ValueError:
                return {"answer": "Gemini is not configured: set GEMINI_API_KEY.",
                        "tool_calls": [], "ok": False, "model": None}
    return {"answer": f"Gemini is busy right now (error {code}). Please try again in a minute.",
            "tool_calls": [], "ok": False, "model": None}
