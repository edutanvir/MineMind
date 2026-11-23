"""src/ai/tools.py - the only functions Gemini is allowed to call (read-only, parameterized SQL)."""
import functools

import duckdb

DB_PATH = "data/minemind.duckdb"
MAX_ROWS = 50
MAX_TREND_ROWS = 600
PLACES = {"sudbury": (46.49, -81.01), "timmins": (48.48, -81.33)}  # approximate town centres
PRODUCT_FORMS = ("concentrates", "recoverable", "refined")
TO_TONNES = {"Kilograms": 0.001, "Grams": 0.000001, "Metric tonnes": 1.0}

NRCAN = {
    "dataset": "NRCan Map 900A (Principal Mineral Areas, Producing Mines, and Oil and Gas Fields)",
    "licence": "Open Government Licence - Canada",
    "caveat": "Significant mapped features only; not a complete list of mines.",
}
STATCAN = {
    "dataset": "Statistics Canada Table 16-10-0019-01",
    "licence": "Statistics Canada Open Licence",
    "caveat": ("Provincial totals, not mine-level. Recent months can be revised. "
               "Concentrates, recoverable and refined are different series: never add them. "
               "'..' means not available and 'x' means suppressed; neither is zero."),
}

CALL_LOG: list[dict] = []  # legacy global log; the app uses tool_set(log) instead
_LOG_CAP = 200


def _row_count(result: dict) -> int:
    return len(result.get("rows") or [])


def logged(fn):
    """Record every call (name, arguments, row count)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        CALL_LOG.append({"tool": fn.__name__, "args": kwargs,
                         "rows": _row_count(result), "error": result.get("error")})
        del CALL_LOG[:-_LOG_CAP]
        return result
    return wrapper


def _query(sql: str, params: list | None = None) -> list[dict]:
    with duckdb.connect(DB_PATH, read_only=True) as con:
        cur = con.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@functools.lru_cache(maxsize=None)
def _distinct(column: str) -> tuple:
    """Valid values of a production-table column, read from the data itself."""
    if column not in {"measure", "commodity", "geography"}:
        raise ValueError(column)
    rows = _query(f"SELECT DISTINCT {column} AS v FROM fact_mineral_production_monthly "
                  f"WHERE {column} IS NOT NULL ORDER BY 1")
    return tuple(r["v"] for r in rows)


def _summarize(series: str, vector, measure: str, points: list[dict]) -> dict:
    """Numbers computed here in Python so the model never does arithmetic."""
    reported = [p for p in points if p["value"] is not None]
    missing = [p for p in points if p["value"] is None]
    by_status: dict[str, int] = {}
    for p in missing:
        key = p["status_symbol"] or "unspecified"
        by_status[key] = by_status.get(key, 0) + 1
    out = {
        "series": series, "vector": vector, "unit": points[0]["unit"],
        "months_returned": len(points), "first_month": points[0]["month"],
        "last_month": points[-1]["month"], "months_with_value": len(reported),
        "months_reported_as_zero": sum(1 for p in reported if p["value"] == 0),
        "months_missing": len(missing), "missing_by_status": by_status,
    }
    if reported:
        nums = [p["value"] for p in reported]
        latest = reported[-1]
        out.update(latest_value_month=latest["month"], latest_value=latest["value"],
                   minimum=min(nums), maximum=max(nums),
                   average_of_reported_months=round(sum(nums) / len(nums), 3))
        if measure != "Closing inventories":
            out["total_of_reported_months"] = round(sum(nums), 3)
        factor = TO_TONNES.get(out["unit"])
        if factor is not None:
            out["latest_value_tonnes"] = round(latest["value"] * factor, 3)
            out["average_tonnes"] = round(out["average_of_reported_months"] * factor, 3)
            if "total_of_reported_months" in out:
                out["total_tonnes"] = round(out["total_of_reported_months"] * factor, 3)
    return out


@logged
def get_production_trend(geography: str, commodity: str, measure: str,
                         last_n_months: int = 60, start_month: str = "",
                         end_month: str = "", product_form: str = "") -> dict:
    """Return monthly Statistics Canada observations, oldest first, plus computed summaries.

    One commodity can have several distinct series (concentrates, recoverable, refined).
    Each series is labelled in `series` and summarised separately in `series_summary`.
    Report series separately; never add them together.

    Args:
        geography: Province or "Canada", e.g. "Ontario".
        commodity: Metal name, e.g. "Nickel" or "Copper".
        measure: "Quantity produced", "Quantity shipped", "Closing inventories" or "Value of shipments".
        last_n_months: Most recent months to return per series (1-240). Default 60.
        start_month: Optional first month, YYYY-MM.
        end_month: Optional last month, YYYY-MM.
        product_form: Optional "concentrates", "recoverable" or "refined". Empty returns every series.
    """
    match = [m for m in _distinct("measure") if m.lower() == measure.strip().lower()]
    if not match:
        return {"error": "Unknown measure.", "valid_measures": list(_distinct("measure")), "rows": []}
    form = product_form.strip().lower()
    if form and form not in PRODUCT_FORMS:
        return {"error": "Unknown product_form.", "valid_product_forms": list(PRODUCT_FORMS), "rows": []}

    where = ["lower(geography) = lower(?)", "lower(commodity) = lower(?)", "measure = ?"]
    params: list = [geography.strip(), commodity.strip(), match[0]]
    if form:
        where.append("lower(commodity_raw) LIKE '%' || lower(?) || '%'")
        params.append(form)
    if start_month:
        where.append("reference_month >= ?")
        params.append(start_month.strip())
    if end_month:
        where.append("reference_month <= ?")
        params.append(end_month.strip())
    n = max(1, min(int(last_n_months), 240))

    fetched = _query(
        f"""SELECT reference_month AS month, commodity_raw AS series, vector,
                   CAST(value AS DOUBLE) AS value, unit, status_symbol
            FROM (SELECT reference_month, commodity_raw, vector, value, unit, status_symbol,
                         row_number() OVER (PARTITION BY commodity_raw, vector
                                            ORDER BY reference_month DESC) AS rn
                  FROM fact_mineral_production_monthly
                  WHERE {" AND ".join(where)}) AS t
            WHERE rn <= {n}
            ORDER BY series, vector, month""", params)

    result: dict = {"source": STATCAN}
    if not fetched:
        result.update(rows=[], note="No rows matched. Retry with one of the valid values.",
                      valid_geographies=list(_distinct("geography")),
                      valid_commodities=list(_distinct("commodity")))
        return result

    grouped: dict[tuple, list[dict]] = {}
    for r in fetched:
        grouped.setdefault((r["series"], r["vector"]), []).append(r)
    per_series_cap = max(1, MAX_TREND_ROWS // len(grouped))
    truncated = any(len(v) > per_series_cap for v in grouped.values())

    rows, summaries = [], []
    for (series, vector), pts in grouped.items():
        pts = pts[-per_series_cap:]
        summaries.append(_summarize(series, vector, match[0], pts))
        rows += [{"month": p["month"], "series": series, "value": p["value"],
                  "unit": p["unit"], "status_symbol": p["status_symbol"]} for p in pts]
    result.update(rows=rows, series_summary=summaries)
    if len(summaries) > 1:
        result["note"] = ("Several distinct series matched. Report each separately with its label "
                          "and unit; never add them together.")
    if truncated:
        result["truncated"] = f"Only the latest {per_series_cap} months per series are shown."
    return result


@logged
def search_mines(province: str = "", commodity: str = "", name_contains: str = "",
                 limit: int = 10) -> dict:
    """Search NRCan Map 900A mapped features. Returns total_matches plus up to `limit` rows.

    Args:
        province: Province name or code, e.g. "Ontario" or "ON". Empty means all.
        commodity: Commodity word, e.g. "nickel". Empty means all.
        name_contains: Part of a feature name. Empty means all.
        limit: Maximum rows to return (1-50).
    """
    limit = max(1, min(int(limit), MAX_ROWS))
    where, params = [], []
    if province:
        where.append("(lower(province) = lower(?) OR lower(province_abr) = lower(?))")
        params += [province.strip(), province.strip()]
    if commodity:
        where.append("lower(commodity_raw) LIKE '%' || lower(?) || '%'")
        params.append(commodity.strip())
    if name_contains:
        where.append("lower(feature_name) LIKE '%' || lower(?) || '%'")
        params.append(name_contains.strip())
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = _query(
        f"""SELECT source_feature_id, feature_name, operator_name, city, province,
                   feature_type, commodity_raw, latitude, longitude
            FROM dim_mine_feature {clause}
            ORDER BY feature_name""", params)
    return {"total_matches": len(rows), "rows": rows[:limit], "source": NRCAN}


@logged
def mines_near_place(place: str, radius_km: float = 50, limit: int = 15) -> dict:
    """Find NRCan Map 900A features within a radius of a Northern Ontario town,
    nearest first. Returns total_within_radius plus up to `limit` rows.

    Args:
        place: "Sudbury" or "Timmins".
        radius_km: Search radius in kilometres (1-300).
        limit: Maximum rows to return (1-50).
    """
    if place.strip().lower() not in PLACES:
        return {"error": f"place must be one of {sorted(PLACES)}", "rows": []}
    lat, lon = PLACES[place.strip().lower()]
    radius_km = max(1.0, min(float(radius_km), 300.0))
    limit = max(1, min(int(limit), MAX_ROWS))
    rows = _query(
        """SELECT * FROM (
             SELECT source_feature_id, feature_name, operator_name, commodity_raw,
                    round(6371 * 2 * asin(sqrt(pow(sin(radians(latitude - ?) / 2), 2)
                      + cos(radians(?)) * cos(radians(latitude))
                        * pow(sin(radians(longitude - ?) / 2), 2))), 1) AS km
             FROM dim_mine_feature
             WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS nearby
           WHERE km <= ? ORDER BY km""",
        [lat, lat, lon, radius_km])
    return {"total_within_radius": len(rows), "rows": rows[:limit], "source": NRCAN}


def tool_set(log: list) -> list:
    """Per-call copies of the tools that record into `log`. Safe when sessions run at once."""
    def wrap(fn):
        raw = fn.__wrapped__

        @functools.wraps(raw)
        def w(*args, **kwargs):
            result = raw(*args, **kwargs)
            log.append({"tool": raw.__name__, "args": kwargs,
                        "rows": _row_count(result), "error": result.get("error")})
            return result
        return w
    return [wrap(search_mines), wrap(get_production_trend), wrap(mines_near_place)]
