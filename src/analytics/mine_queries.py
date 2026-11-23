"""Pure helpers for NRCan mine features (no Streamlit, easy to test)."""
from __future__ import annotations

import re

import pandas as pd

# A comma that is NOT inside parentheses, e.g. "Potash (potassium chloride), salt".
_COMMA_OUTSIDE_PARENS = re.compile(r",(?![^()]*\))")


def split_commodities(commodity_raw) -> list[str]:
    """Split the source commodity text into a clean, de-duplicated list (source order)."""
    if not isinstance(commodity_raw, str) or not commodity_raw.strip():
        return []
    items: list[str] = []
    for part in _COMMA_OUTSIDE_PARENS.split(commodity_raw):
        part = part.strip()
        if not part:
            continue
        label = part[0].upper() + part[1:]
        if label not in items:
            items.append(label)
    return items


def primary_commodity(commodity_raw) -> str:
    """First commodity listed in the source record (the source lists the main product first)."""
    items = split_commodities(commodity_raw)
    return items[0] if items else "Not stated"


def with_primary_commodity(mines: pd.DataFrame) -> pd.DataFrame:
    """Return a copy where `commodity_normalized` is the first listed commodity.

    The Gold column picks a commodity by dictionary order, so a nickel mine that also lists
    gold can show up as "Gold". The original value is kept in `commodity_family`.
    """
    out = mines.copy()
    if "commodity_raw" not in out.columns:
        return out
    if "commodity_normalized" in out.columns:
        out["commodity_family"] = out["commodity_normalized"]
    out["commodity_normalized"] = out["commodity_raw"].map(primary_commodity)
    return out
