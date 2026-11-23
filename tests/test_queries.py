"""Tests for mine helpers, usage guard and the Gemini tools (real DuckDB file, tiny fixtures)."""
import inspect

import duckdb
import pytest

from src.ai import guard, tools
from src.analytics.mine_queries import primary_commodity, split_commodities, with_primary_commodity

import pandas as pd

NICKEL_RAW = "Nickel, copper, platinum group metals, gold, silver, cobalt, selenium, tellurium"


# ---------- mine helpers ----------
@pytest.mark.parametrize("raw, expected", [
    (NICKEL_RAW, "Nickel"),
    ("Gold, silver", "Gold"),
    ("Potash (potassium chloride), salt", "Potash (potassium chloride)"),
    ("coal (metallurgical)", "Coal (metallurgical)"),
    ("", "Not stated"),
    (None, "Not stated"),
    (float("nan"), "Not stated"),
])
def test_primary_commodity(raw, expected):
    assert primary_commodity(raw) == expected


def test_split_commodities_keeps_parentheses_and_dedupes():
    assert split_commodities("Potash (potassium chloride), salt, Salt") == ["Potash (potassium chloride)", "Salt"]
    assert len(split_commodities(NICKEL_RAW)) == 8


def test_with_primary_commodity_fixes_nickel_mine_labelled_gold():
    df = pd.DataFrame({"commodity_raw": [NICKEL_RAW], "commodity_normalized": ["Gold"]})
    out = with_primary_commodity(df)
    assert out.loc[0, "commodity_normalized"] == "Nickel"
    assert out.loc[0, "commodity_family"] == "Gold"
    assert df.loc[0, "commodity_normalized"] == "Gold"  # input not mutated


# ---------- usage guard ----------
def test_daily_guard_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(guard, "DAILY_LIMIT", 2)
    monkeypatch.setattr(guard, "_day", None)
    monkeypatch.setattr(guard, "_count", 0)
    assert [guard.take_daily_slot() for _ in range(3)] == [True, True, False]


# ---------- Gemini tools against a tiny database ----------
MINES = [
    ("1", "Copper Cliff Mine", "Vale", "Sudbury", "Ontario", "ON", "Metal mines", NICKEL_RAW, 46.47, -81.07),
    ("2", "Creighton Mine", "Vale", "Sudbury", "Ontario", "ON", "Metal mines", "Nickel", 46.46, -81.19),
    ("3", "Kidd Mine", "Glencore", "Timmins", "Ontario", "ON", "Metal mines", "Zinc, copper", 48.69, -81.37),
    ("4", "Raglan", "Glencore", "Nunavik", "Quebec", "QC", "Metal mines", "Nickel", 61.69, -73.68),
]
CONC, RECOV = "Nickel, concentrates (kilograms)", "Nickel, recoverable (kilograms)"


def _fact_rows():
    rows = []
    for i in range(1, 25):  # 24 months: 2025-01 .. 2026-12
        month = f"{2025 + (i - 1) // 12}-{(i - 1) % 12 + 1:02d}"
        rows.append((month, "Ontario", "Nickel", "Quantity produced", CONC, "v1", 10000.0 * i, "Kilograms", ""))
        rows.append((month, "Ontario", "Nickel", "Quantity produced", RECOV, "v2", 1000.0 * i, "Kilograms", ""))
    # month 2026-03 (index 15) recoverable: suppressed; month 2026-04 recoverable: reported zero
    rows = [r for r in rows if not (r[0] == "2026-03" and r[4] == RECOV and True)]
    rows.append(("2026-03", "Ontario", "Nickel", "Quantity produced", RECOV, "v2", None, "Kilograms", "x"))
    rows = [(*r[:6], 0.0, *r[7:]) if (r[0] == "2026-04" and r[4] == RECOV) else r for r in rows]
    rows.append(("2026-12", "Ontario", "Nickel", "Closing inventories", CONC, "v3", 2050000.0, "Kilograms", ""))
    rows.append(("2026-12", "Ontario", "Nickel", "Value of shipments", "Nickel, concentrates (dollars)", "v4", 9.0, "Dollars", ""))
    rows.append(("2026-12", "Quebec", "Copper", "Quantity produced", "Copper, recoverable (kilograms)", "v5", 5.0, "Kilograms", ""))
    return rows


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE dim_mine_feature(source_feature_id VARCHAR, feature_name VARCHAR,
        operator_name VARCHAR, city VARCHAR, province VARCHAR, province_abr VARCHAR,
        feature_type VARCHAR, commodity_raw VARCHAR, latitude DOUBLE, longitude DOUBLE)""")
    con.executemany("INSERT INTO dim_mine_feature VALUES (?,?,?,?,?,?,?,?,?,?)", MINES)
    con.execute("""CREATE TABLE fact_mineral_production_monthly(reference_month VARCHAR, geography VARCHAR,
        commodity VARCHAR, measure VARCHAR, commodity_raw VARCHAR, vector VARCHAR, value DOUBLE,
        unit VARCHAR, status_symbol VARCHAR)""")
    con.executemany("INSERT INTO fact_mineral_production_monthly VALUES (?,?,?,?,?,?,?,?,?)", _fact_rows())
    con.close()
    monkeypatch.setattr(tools, "DB_PATH", str(path))
    tools._distinct.cache_clear()
    tools.CALL_LOG.clear()
    yield path
    tools._distinct.cache_clear()


def _by_series(result):
    return {s["series"]: s for s in result["series_summary"]}


def test_two_series_are_never_merged(db):
    r = tools.get_production_trend("ontario", "NICKEL", "quantity produced", last_n_months=6)
    assert {row["series"] for row in r["rows"]} == {CONC, RECOV}
    assert len(r["series_summary"]) == 2
    assert "never add" in r["note"].lower()
    for series in (CONC, RECOV):
        months = [x["month"] for x in r["rows"] if x["series"] == series]
        assert months == sorted(months) and len(months) == 6
        assert months[-1] == "2026-12"          # latest months kept
    assert r["source"]["dataset"].startswith("Statistics Canada")


def test_last_n_months_is_per_series_and_clamped(db):
    r = tools.get_production_trend("Ontario", "Nickel", "Quantity produced", last_n_months=9999)
    assert len(r["rows"]) == 48                 # 24 months x 2 series
    r = tools.get_production_trend("Ontario", "Nickel", "Quantity produced", last_n_months=-5)
    assert len(r["rows"]) == 2                  # 1 month x 2 series


def test_summary_numbers_and_tonnes(db):
    r = tools.get_production_trend("Ontario", "Nickel", "Quantity produced", product_form="concentrates")
    s = _by_series(r)[CONC]
    values = [10000.0 * i for i in range(1, 25)]
    assert s["months_with_value"] == 24 and s["months_missing"] == 0
    assert s["latest_value"] == 240000.0 and s["latest_value_month"] == "2026-12"
    assert s["total_of_reported_months"] == sum(values)
    assert s["average_of_reported_months"] == pytest.approx(sum(values) / 24)
    assert s["latest_value_tonnes"] == 240.0
    assert s["total_tonnes"] == pytest.approx(sum(values) / 1000)
    assert s["minimum"] == 10000.0 and s["maximum"] == 240000.0
    assert s["unit"] == "Kilograms" and s["vector"] == "v1"


def test_suppressed_and_zero_are_not_confused(db):
    r = tools.get_production_trend("Ontario", "Nickel", "Quantity produced", product_form="recoverable")
    s = _by_series(r)[RECOV]
    assert s["months_missing"] == 1 and s["missing_by_status"] == {"x": 1}
    assert s["months_reported_as_zero"] == 1
    assert s["months_with_value"] == 23          # zero counts as reported, suppressed does not
    row = next(x for x in r["rows"] if x["month"] == "2026-03")
    assert row["value"] is None and row["status_symbol"] == "x"


def test_closing_inventories_has_no_total(db):
    r = tools.get_production_trend("Ontario", "Nickel", "Closing inventories")
    s = r["series_summary"][0]
    assert "total_of_reported_months" not in s and s["latest_value"] == 2050000.0


def test_dollars_have_no_tonnes(db):
    s = tools.get_production_trend("Ontario", "Nickel", "Value of shipments")["series_summary"][0]
    assert s["unit"] == "Dollars" and "latest_value_tonnes" not in s


def test_date_window_and_bad_inputs(db):
    r = tools.get_production_trend("Ontario", "Nickel", "Quantity produced", product_form="concentrates",
                                   start_month="2025-01", end_month="2025-03")
    assert [x["month"] for x in r["rows"]] == ["2025-01", "2025-02", "2025-03"]
    bad = tools.get_production_trend("Ontario", "Nickel", "Banana")
    assert "Quantity produced" in bad["valid_measures"] and bad["rows"] == []
    bad = tools.get_production_trend("Ontario", "Nickel", "Quantity produced", product_form="gold-plated")
    assert "recoverable" in bad["valid_product_forms"]
    empty = tools.get_production_trend("Atlantis", "Nickel", "Quantity produced")
    assert empty["rows"] == [] and "Ontario" in empty["valid_geographies"]


def test_values_are_parameters_not_sql(db):
    r = tools.get_production_trend("Ontario'; DROP TABLE dim_mine_feature;--", "Nickel", "Quantity produced")
    assert r["rows"] == []
    assert tools.search_mines()["total_matches"] == 4


def test_search_mines(db):
    assert tools.search_mines(province="ON")["total_matches"] == 3
    r = tools.search_mines(province="ontario", commodity="nickel", limit=1)
    assert r["total_matches"] == 2 and len(r["rows"]) == 1
    assert tools.search_mines(name_contains="CREIGH")["rows"][0]["operator_name"] == "Vale"
    assert len(tools.search_mines(limit=9999)["rows"]) <= tools.MAX_ROWS


def test_mines_near_place(db):
    r = tools.mines_near_place("Sudbury", radius_km=50)
    assert [x["feature_name"] for x in r["rows"]] == ["Copper Cliff Mine", "Creighton Mine"]
    assert r["total_within_radius"] == 2
    assert [x["km"] for x in r["rows"]] == sorted(x["km"] for x in r["rows"])
    assert "error" in tools.mines_near_place("Toronto")


def test_tool_set_logs_privately_and_keeps_signatures(db):
    log_a, log_b = [], []
    a = {f.__name__: f for f in tools.tool_set(log_a)}
    b = {f.__name__: f for f in tools.tool_set(log_b)}
    a["search_mines"](province="ON")
    b["mines_near_place"](place="Sudbury")
    assert [c["tool"] for c in log_a] == ["search_mines"]
    assert [c["tool"] for c in log_b] == ["mines_near_place"]
    for f in a.values():
        sig = inspect.signature(f)
        assert f.__doc__ and all(p.annotation is not inspect.Parameter.empty for p in sig.parameters.values())
