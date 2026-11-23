"""src/ai/gemini_agent.py - sends a question to Gemini, which may call the tools."""
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src.ai import tools

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

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
        _client = genai.Client()  # reads GEMINI_API_KEY from the environment
    return _client


def ask(question: str) -> dict:
    """Return {"answer": str, "tool_calls": list}. The log is private to this call."""
    log: list[dict] = []
    try:
        response = _get_client().models.generate_content(
            model=MODEL,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                tools=tools.tool_set(log),
            ),
        )
        answer = response.text or "Gemini returned no text. Try rephrasing the question."
    except errors.APIError as e:
        answer = f"Gemini API error ({getattr(e, 'code', '?')}). Wait a minute and retry."
    except ValueError:
        answer = "Gemini is not configured: set GEMINI_API_KEY."
    return {"answer": answer, "tool_calls": log}
