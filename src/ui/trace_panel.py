"""Show-your-work panel: renders the tool calls Gemini made for one answer.

Usage in pages/3_Ask_MineMind.py, right after you show the answer:

    from src.ui.trace_panel import render_tool_trace
    render_tool_trace(log)        # `log` is the same list you pass to tool_set(log)

The panel reads the entries that `tool_set(log)` already records
(tool, args, rows, error), so src/ai/tools.py needs no change.
"""
from __future__ import annotations

import json

from src.ai.tools import NRCAN, STATCAN

TOOL_META = {
    "get_production_trend": ("Statistics Canada production series", STATCAN),
    "search_mines": ("NRCan Map 900A feature search", NRCAN),
    "mines_near_place": ("NRCan Map 900A radius search", NRCAN),
}


def summarize_trace(log: list[dict] | None) -> dict:
    """Pure helper (no Streamlit): counts, datasets used and errors for one answer."""
    calls = list(log or [])
    datasets: list[dict] = []
    seen: set[str] = set()
    for c in calls:
        meta = TOOL_META.get(c.get("tool"))
        if meta and meta[1]["dataset"] not in seen:
            seen.add(meta[1]["dataset"])
            datasets.append(meta[1])
    return {
        "calls": len(calls),
        "rows": sum(int(c.get("rows") or 0) for c in calls),
        "errors": [c for c in calls if c.get("error")],
        "datasets": datasets,
    }


def _clean_args(args: dict | None) -> dict:
    return {k: v for k, v in (args or {}).items() if v not in ("", None)}


def render_tool_trace(log: list[dict] | None, *, title: str = "How MineMind answered this", expanded: bool = False) -> None:
    import streamlit as st  # imported here so summarize_trace stays importable without Streamlit

    calls = list(log or [])
    if not calls:
        st.warning(
            "No data tools were called for this answer, so it is not backed by the MineMind data. "
            "Treat it as general knowledge."
        )
        return

    info = summarize_trace(calls)
    with st.expander(f"🔎 {title}  ·  {info['calls']} tool call(s), {info['rows']} row(s)", expanded=expanded):
        st.caption(
            "Gemini chose these read-only tools. Totals and conversions were computed in Python "
            "from the Gold layer, not by the model."
        )
        for i, c in enumerate(calls, 1):
            label, _ = TOOL_META.get(c.get("tool"), (c.get("tool"), None))
            st.markdown(f"**{i}. `{c.get('tool')}`**  ·  {label}")
            st.code(json.dumps(_clean_args(c.get("args")), indent=2, default=str), language="json")
            if c.get("error"):
                st.error(f"Tool returned an error: {c['error']}. Gemini may have retried with valid values.")
            else:
                st.caption(f"Returned {c.get('rows', 0)} row(s).")
        st.markdown("**Sources and caveats**")
        for d in info["datasets"]:
            st.caption(f"{d['dataset']}  ·  {d['licence']}")
            st.caption(f"Caveat: {d['caveat']}")
