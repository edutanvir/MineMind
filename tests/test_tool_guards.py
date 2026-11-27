"""Offline guardrail tests for src/ai/tools.py. No API key needed.

Tests marked `needs_db` run against data/minemind.duckdb and are skipped if it is missing.
Run from the repo root: pytest -q tests/test_tool_guards.py
"""
import pathlib

import pytest

pytest.importorskip("duckdb")
from src.ai import tools  # noqa: E402

needs_db = pytest.mark.skipif(
    not pathlib.Path(tools.DB_PATH).exists(), reason="data/minemind.duckdb has not been built"
)


def _pt(month, value, unit="Kilograms", status=None):
    return {"month": month, "value": value, "unit": unit, "status_symbol": status}


# ---------- pure logic (no database) ----------

def test_summarize_converts_units_and_totals_in_python():
    pts = [_pt("2024-01", 1000.0), _pt("2024-02", 0.0), _pt("2024-05", 2000.0)]
    out = tools._summarize("Nickel concentrates", "v1", "Quantity produced", pts)
    assert out["latest_value_month"] == "2024-05"
    assert out["total_of_reported_months"] == pytest.approx(3000.0)
    assert out["total_tonnes"] == pytest.approx(3.0)
    assert out["latest_value_tonnes"] == pytest.approx(2.0)
    assert out["average_of_reported_months"] == pytest.approx(1000.0)


def test_missing_months_are_counted_not_treated_as_zero():
    pts = [_pt("2024-01", 5.0), _pt("2024-02", None, status="x"),
           _pt("2024-03", None, status=".."), _pt("2024-04", 0.0)]
    out = tools._summarize("Copper", "v2", "Quantity produced", pts)
    assert out["months_missing"] == 2
    assert out["missing_by_status"] == {"x": 1, "..": 1}
    assert out["months_reported_as_zero"] == 1       # a real reported zero is not the same as missing
    assert out["months_with_value"] == 2
    assert out["minimum"] == 0.0


def test_inventories_are_never_totalled():
    pts = [_pt("2024-01", 10.0), _pt("2024-02", 20.0)]
    out = tools._summarize("Nickel", "v3", "Closing inventories", pts)
    assert "total_of_reported_months" not in out
    assert "total_tonnes" not in out


def test_unknown_unit_gets_no_tonne_conversion():
    out = tools._summarize("Gold", "v4", "Value of shipments", [_pt("2024-01", 100.0, unit="Dollars")])
    assert "latest_value_tonnes" not in out


def test_distinct_only_accepts_allowlisted_columns():
    with pytest.raises(ValueError):
        tools._distinct("value; DROP TABLE dim_mine_feature")


def test_unknown_place_is_refused_without_touching_the_database():
    res = tools.mines_near_place("Toronto")
    assert res["rows"] == []
    assert "error" in res


def test_tool_set_records_calls_in_the_given_log_only():
    log: list[dict] = []
    before = len(tools.CALL_LOG)
    wrapped = {fn.__name__: fn for fn in tools.tool_set(log)}
    assert set(wrapped) == {"search_mines", "get_production_trend", "mines_near_place"}
    wrapped["mines_near_place"](place="Atlantis")
    assert len(log) == 1
    assert log[0]["tool"] == "mines_near_place" and log[0]["rows"] == 0 and log[0]["error"]
    assert len(tools.CALL_LOG) == before             # per-session log leaves the global log alone


# ---------- against the real database ----------

@needs_db
def test_connection_is_read_only():
    with pytest.raises(Exception):
        tools._query("CREATE TABLE should_not_exist (i INTEGER)")


@needs_db
def test_sql_injection_strings_are_inert():
    res = tools.search_mines(name_contains="'; DROP TABLE dim_mine_feature; --")
    assert res["total_matches"] == 0 and res["rows"] == []
    assert tools._query("SELECT count(*) AS n FROM dim_mine_feature")[0]["n"] > 0


@needs_db
def test_limits_are_clamped():
    assert len(tools.search_mines(limit=10_000)["rows"]) <= tools.MAX_ROWS
    res = tools.mines_near_place("Sudbury", radius_km=99_999, limit=10_000)
    assert len(res["rows"]) <= tools.MAX_ROWS
    assert all(r["km"] <= 300 for r in res["rows"])


@needs_db
def test_nearest_first():
    kms = [r["km"] for r in tools.mines_near_place("Sudbury", radius_km=300, limit=50)["rows"]]
    assert kms == sorted(kms)


@needs_db
def test_every_result_carries_its_source_and_caveat():
    for res in (tools.search_mines(limit=1), tools.mines_near_place("Timmins", limit=1)):
        assert res["source"]["licence"] and res["source"]["caveat"]


@needs_db
def test_bad_measure_returns_valid_values_for_a_retry():
    res = tools.get_production_trend("Ontario", "Nickel", "not a real measure")
    assert "error" in res and res["valid_measures"]


@needs_db
def test_bad_product_form_is_rejected():
    measure = tools._distinct("measure")[0]
    res = tools.get_production_trend("Ontario", "Nickel", measure, product_form="sparkles")
    assert "error" in res and res["valid_product_forms"]


@needs_db
def test_multiple_series_are_labelled_and_never_merged():
    measure = tools._distinct("measure")[0]
    res = tools.get_production_trend("Ontario", "Nickel", measure)
    if not res.get("series_summary"):
        pytest.skip("no Ontario nickel series in this database")
    keys = [(s["series"], s["vector"]) for s in res["series_summary"]]
    assert len(keys) == len(set(keys))
    if len(keys) > 1:
        assert "never add" in res["note"].lower()
