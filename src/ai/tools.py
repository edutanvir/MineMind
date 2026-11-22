"""src/ai/tools.py - the only functions Gemini is allowed to call (read-only)."""
import functools

import duckdb

DB_PATH = "data/minemind.duckdb"
MAX_ROWS = 50
PLACES = {"sudbury": (46.49, -81.01), "timmins": (48.48, -81.33)}  # approximate town centres

NRCAN = {
    "dataset": "NRCan Map 900A (Principal Mineral Areas, Producing Mines, and Oil and Gas Fields)",
    "licence": "Open Government Licence - Canada",
    "caveat": "Significant mapped features only; not a complete list of mines.",
}
STATCAN = {
    "dataset": "Statistics Canada Table 16-10-0019-01",
    "licence": "Statistics Canada Open Licence",
    "caveat": "Provincial totals, not mine-level. Recent months can be revised. Suppressed values are not zero.",
}

CALL_LOG: list[dict] = []  # the Streamlit page reads this to show "Tools used"


def logged(fn):
    """Record every call (name, arguments, row count) so the UI can display it."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        CALL_LOG.append({"tool": fn.__name__, "args": kwargs,
                         "rows": len(result.get("rows", [])), "error": result.get("error")})
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



def _production_series(geography: str, commodity: str, measure: str,
                       start_month: str = "", end_month: str = "") -> list[dict]:
    """Return available statistical series for a geography, commodity and measure."""
    where = [
        "lower(geography) = lower(?)",
        "lower(commodity) = lower(?)",
        "measure = ?",
    ]
    params = [geography.strip(), commodity.strip(), measure]

    if start_month:
        where.append("reference_month >= ?")
        params.append(start_month.strip())

    if end_month:
        where.append("reference_month <= ?")
        params.append(end_month.strip())

    return _query(
        f"""
        SELECT DISTINCT
            commodity_raw AS series,
            unit,
            vector,
            coordinate
        FROM fact_mineral_production_monthly
        WHERE {" AND ".join(where)}
        ORDER BY series, unit
        """,
        params,
    )


@logged
def get_production_trend(geography: str, commodity: str, measure: str,
                         last_n_months: int = 60, start_month: str = "",
                         end_month: str = "", series: str = "",
                         unit: str = "") -> dict:
    """Return monthly production observations without mixing statistical series.

    Args:
        geography: Province or "Canada", e.g. "Ontario".
        commodity: Commodity name, e.g. "Nickel" or "Copper".
        measure: Statistical measure, e.g. "Quantity produced".
        last_n_months: Number of distinct calendar months (1-240).
        start_month: Optional first month, YYYY-MM.
        end_month: Optional last month, YYYY-MM.
        series: Optional exact commodity_raw series, e.g.
                "Nickel, concentrates (kilograms)".
        unit: Optional exact unit to distinguish series.
    """
    match = [
        m for m in _distinct("measure")
        if m.lower() == measure.strip().lower()
    ]

    if not match:
        return {
            "error": "Unknown measure.",
            "valid_measures": list(_distinct("measure")),
            "rows": [],
        }

    measure = match[0]
    available_series = _production_series(
        geography, commodity, measure, start_month, end_month
    )

    if not available_series:
        return {
            "rows": [],
            "note": "No matching production series were found.",
            "valid_geographies": list(_distinct("geography")),
            "valid_commodities": list(_distinct("commodity")),
            "source": STATCAN,
        }

    # Apply optional series and unit selection.
    candidates = available_series

    if series.strip():
        candidates = [
            item for item in candidates
            if item["series"].lower() == series.strip().lower()
        ]

    if unit.strip():
        candidates = [
            item for item in candidates
            if item["unit"].lower() == unit.strip().lower()
        ]

    if not candidates:
        return {
            "error": "No production series matched the requested series and unit.",
            "available_series": available_series,
            "rows": [],
            "source": STATCAN,
        }

    # Never silently combine different statistical series or units.
    distinct_choices = {
        (
            item["series"],
            item["unit"],
            item["vector"],
            item["coordinate"],
        )
        for item in candidates
    }

    if len(distinct_choices) > 1:
        return {
            "requires_series": True,
            "note": (
                "Multiple statistical series match this request. "
                "Select one series, unit, and statistical identifier. "
                "These series must not be combined."
            ),
            "available_series": candidates,
            "rows": [],
            "source": STATCAN,
        }

    selected = candidates[0]
    selected_series = selected["series"]
    selected_unit = selected["unit"]
    selected_vector = selected["vector"]
    selected_coordinate = selected["coordinate"]

    where = [
        "lower(geography) = lower(?)",
        "lower(commodity) = lower(?)",
        "measure = ?",
        "commodity_raw = ?",
        "unit = ?",
        "vector IS NOT DISTINCT FROM ?",
        "coordinate IS NOT DISTINCT FROM ?",
    ]

    params = [
        geography.strip(),
        commodity.strip(),
        measure,
        selected_series,
        selected_unit,
        selected_vector,
        selected_coordinate,
    ]

    if start_month:
        where.append("reference_month >= ?")
        params.append(start_month.strip())

    if end_month:
        where.append("reference_month <= ?")
        params.append(end_month.strip())

    n = max(1, min(int(last_n_months), 240))

    # First select the latest N DISTINCT months.
    # Then return every observation for the selected series in those months.
    rows = _query(
        f"""
        WITH matching_rows AS (
            SELECT
                reference_month,
                commodity_raw,
                CAST(value AS DOUBLE) AS value,
                unit,
                measure,
                status_symbol,
                symbol,
                vector,
                coordinate
            FROM fact_mineral_production_monthly
            WHERE {" AND ".join(where)}
        ),
        selected_months AS (
            SELECT DISTINCT reference_month
            FROM matching_rows
            ORDER BY reference_month DESC
            LIMIT ?
        )
        SELECT
            mr.reference_month AS month,
            mr.commodity_raw AS series,
            mr.value,
            mr.unit,
            mr.measure,
            mr.status_symbol,
            mr.symbol,
            mr.vector,
            mr.coordinate
        FROM matching_rows AS mr
        INNER JOIN selected_months AS sm
            ON mr.reference_month = sm.reference_month
        ORDER BY mr.reference_month ASC
        """,
        params + [n],
    )

    return {
        "rows": rows,
        "series": selected_series,
        "unit": selected_unit,
        "months_requested": n,
        "months_returned": len({row["month"] for row in rows}),
        "source": STATCAN,
    }


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
