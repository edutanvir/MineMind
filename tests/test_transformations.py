"""tests/test_transformations.py

Unit tests for src/transformation/clean_data.py.

They use tiny in-memory tables, so they need no downloaded data, no network
and no Gemini key. Run from the project root with:  python -m pytest -v
"""
import pandas as pd
import pytest

from src.transformation.clean_data import (
    build_gold_models,
    extract_primary_commodity,
    process_nrcan_silver,
    process_statcan_silver,
)

# Columns the Gemini tools (src/ai/tools.py) query. If a rename removes one of
# them, the contract test at the bottom fails before the app does.
TOOL_DIM_COLUMNS = {
    "source_feature_id", "feature_name", "province", "feature_type",
    "commodity_raw", "latitude", "longitude",
}
TOOL_FACT_COLUMNS = {
    "reference_month", "geography", "commodity", "measure",
    "value", "unit", "status_symbol",
}

NRCAN_SILVER_COLUMNS = [
    "feature_key", "source_feature_id", "feature_name", "operator_name",
    "province", "province_abr", "city", "feature_type", "commodity_raw",
    "commodity_normalized", "facilities_type", "latitude", "longitude",
    "website", "source_layer", "source_vintage",
]
STATCAN_SILVER_COLUMNS = [
    "reference_month", "geography", "commodity", "commodity_raw", "measure",
    "value", "unit", "status_symbol", "symbol", "vector", "coordinate",
    "source_table", "retrieval_date",
]


# ---------------------------------------------------------------- helpers
def nrcan_row(**overrides) -> dict:
    """One valid raw NRCan row (text padded with spaces on purpose)."""
    row = {
        "count": 1,
        "operation_name_en": "  Test Mine A ",
        "operator_owners_en": " Test Operator ",
        "province_en": " Ontario ",
        "province_abr": " on ",
        "city_en": " Testville ",
        "operation_group_en": " Metal mine ",
        "product_en_spelt": " Nickel, Copper ",
        "facilities_code_en_spelt": " Underground ",
        "latitude": 46.5,
        "longitude": -81.0,
        "website": " https://example.com ",
    }
    row.update(overrides)
    return row


def nrcan_layers(*rows) -> dict:
    return {"ProducingMines": pd.DataFrame(list(rows))}


def statcan_row(**overrides) -> dict:
    """One valid raw Statistics Canada row. Every value is text, as when the
    CSV is read with dtype=str."""
    row = {
        "REF_DATE": "2024-01",
        "GEO": "Ontario",
        "Products": "Nickel",
        "Variables": "Quantity produced",
        "UOM": "Tonnes",
        "VALUE": "1,234.5",
        "STATUS": "",
        "SYMBOL": "",
        "VECTOR": "v123",
        "COORDINATE": "7.1.1",
    }
    row.update(overrides)
    return row


def statcan_frame(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ------------------------------------------------ extract_primary_commodity
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Gold", "Gold"),
        ("  nickel ", "Nickel"),
        ("Iron ore", "Iron Ore"),
        ("Platinum group metals", "Platinum Group Metals"),
        ("Palladium", "Platinum Group Metals"),
        ("Tungsten, Tin", "Tungsten"),  # not in the mapping: text before the comma
        ("", "Other"),
        (None, "Other"),
        (42, "Other"),
    ],
)
def test_extract_primary_commodity(text, expected):
    assert extract_primary_commodity(text) == expected


def test_multi_commodity_text_uses_mapping_priority_not_text_order():
    """Pins CURRENT behaviour (not necessarily the ideal one): the first key
    in COMMODITY_MAPPING that appears anywhere in the text wins, not the first
    commodity written in the text. If you change the rule, update this test."""
    assert extract_primary_commodity("Copper, Nickel") == "Nickel"
    assert extract_primary_commodity("Copper, Gold") == "Gold"


# ------------------------------------------------------ process_nrcan_silver
def test_nrcan_standardizes_text_ids_and_columns():
    silver, meta = process_nrcan_silver(nrcan_layers(nrcan_row()))

    assert list(silver.columns) == NRCAN_SILVER_COLUMNS
    row = silver.iloc[0]
    assert row["feature_key"] == "MINE_0001"
    assert row["source_feature_id"] == 1
    assert row["feature_name"] == "Test Mine A"
    assert row["operator_name"] == "Test Operator"
    assert row["province"] == "Ontario"
    assert row["province_abr"] == "ON"
    assert row["commodity_raw"] == "Nickel, Copper"
    assert row["commodity_normalized"] == "Nickel"
    assert row["website"] == "https://example.com"
    assert row["source_layer"] == "ProducingMines"
    assert meta == {
        "input_rows": 1,
        "output_rows": 1,
        "rejected_rows": 0,
        "rejection_reasons": "None",
    }


def test_nrcan_rejects_missing_and_out_of_bounds_coordinates():
    layers = nrcan_layers(
        nrcan_row(count=1),                    # valid
        nrcan_row(count=2, latitude=None),     # missing latitude
        nrcan_row(count=3, longitude=None),    # missing longitude
        nrcan_row(count=4, latitude=10.0),     # south of the allowed range
        nrcan_row(count=5, latitude=90.0),     # north of the allowed range
        nrcan_row(count=6, longitude=-10.0),   # east of the allowed range
        nrcan_row(count=7, longitude=-160.0),  # west of the allowed range
    )
    silver, meta = process_nrcan_silver(layers)

    assert silver["source_feature_id"].tolist() == [1]
    assert meta["input_rows"] == 7
    assert meta["output_rows"] == 1
    assert meta["rejected_rows"] == 6
    assert meta["input_rows"] == meta["output_rows"] + meta["rejected_rows"]
    assert meta["rejection_reasons"] == "6 rows with invalid/out-of-bound coordinates"


def test_nrcan_keeps_coordinates_exactly_on_the_bounds():
    layers = nrcan_layers(
        nrcan_row(count=1, latitude=40.0),
        nrcan_row(count=2, latitude=85.0),
        nrcan_row(count=3, longitude=-145.0),
        nrcan_row(count=4, longitude=-50.0),
    )
    silver, meta = process_nrcan_silver(layers)

    assert silver["source_feature_id"].tolist() == [1, 2, 3, 4]
    assert meta["rejected_rows"] == 0


def test_nrcan_missing_layer_raises():
    with pytest.raises(ValueError, match="ProducingMines"):
        process_nrcan_silver({})


def test_nrcan_does_not_modify_raw_input():
    layers = nrcan_layers(nrcan_row(), nrcan_row(count=2, latitude=None))
    before = layers["ProducingMines"].copy(deep=True)

    process_nrcan_silver(layers)

    pd.testing.assert_frame_equal(layers["ProducingMines"], before)


# --------------------------------------------------- process_statcan_silver
def test_statcan_blank_value_stays_missing_never_zero():
    raw = statcan_frame(
        statcan_row(REF_DATE="2024-01", VALUE="1,234.5"),
        statcan_row(REF_DATE="2024-02", VALUE=""),
        statcan_row(REF_DATE="2024-03", VALUE="0"),
        statcan_row(REF_DATE="2024-04", VALUE=".."),
    )
    silver, _ = process_statcan_silver(raw)
    by_month = silver.set_index("reference_month")["value"]

    assert by_month["2024-01"] == 1234.5  # thousands separator removed
    assert pd.isna(by_month["2024-02"])   # blank -> missing, not 0
    assert by_month["2024-03"] == 0.0     # a real zero stays a zero
    assert pd.isna(by_month["2024-04"])   # non-numeric -> missing, not 0
    assert silver["value"].isna().sum() == 2


def test_statcan_keeps_status_symbol_and_unit():
    raw = statcan_frame(statcan_row(VALUE="", STATUS="x", SYMBOL=".."))
    silver, _ = process_statcan_silver(raw)
    row = silver.iloc[0]

    assert row["status_symbol"] == "x"
    assert row["symbol"] == ".."
    assert row["unit"] == "Tonnes"


def test_statcan_rejects_malformed_reference_dates():
    raw = statcan_frame(
        statcan_row(REF_DATE="2024-01"),  # valid
        statcan_row(REF_DATE="2024"),
        statcan_row(REF_DATE="2024-1"),
        statcan_row(REF_DATE="Jan 2024"),
        statcan_row(REF_DATE=""),
    )
    silver, meta = process_statcan_silver(raw)

    assert silver["reference_month"].tolist() == ["2024-01"]
    assert meta["input_rows"] == 5
    assert meta["output_rows"] == 1
    assert meta["rejected_rows"] == 4
    assert meta["input_rows"] == meta["output_rows"] + meta["rejected_rows"]
    assert meta["rejection_reasons"] == "4 rows with invalid REF_DATE format"


def test_statcan_rejects_impossible_months():
    raw = statcan_frame(
        statcan_row(REF_DATE="2024-13"),
        statcan_row(REF_DATE="2024-00"),
        statcan_row(REF_DATE="2024-12"),
    )
    silver, meta = process_statcan_silver(raw)

    assert silver["reference_month"].tolist() == ["2024-12"]
    assert meta["rejected_rows"] == 2


def test_statcan_standardizes_names_commodity_and_columns():
    raw = statcan_frame(
        statcan_row(GEO=" Ontario ", Products=" Nickel ", Variables=" Quantity shipped ")
    )
    silver, meta = process_statcan_silver(raw)
    row = silver.iloc[0]

    assert list(silver.columns) == STATCAN_SILVER_COLUMNS
    assert row["geography"] == "Ontario"
    assert row["commodity_raw"] == "Nickel"
    assert row["commodity"] == "Nickel"
    assert row["measure"] == "Quantity shipped"
    assert row["source_table"] == "16-10-0019-01"
    assert meta["rejection_reasons"] == "None"


def test_statcan_does_not_modify_raw_input():
    raw = statcan_frame(statcan_row(), statcan_row(REF_DATE="bad"))
    before = raw.copy(deep=True)

    process_statcan_silver(raw)

    pd.testing.assert_frame_equal(raw, before)


# ---------------------------------------------------------- build_gold_models
def _silver_pair():
    silver_mines, _ = process_nrcan_silver(nrcan_layers(nrcan_row()))
    silver_statcan, _ = process_statcan_silver(statcan_frame(statcan_row()))
    return silver_mines, silver_statcan


def test_gold_models_are_independent_copies_of_silver():
    silver_mines, silver_statcan = _silver_pair()

    dim, fact = build_gold_models(silver_mines, silver_statcan)

    pd.testing.assert_frame_equal(dim, silver_mines)
    pd.testing.assert_frame_equal(fact, silver_statcan)
    dim.loc[:, "feature_name"] = "changed"
    fact.loc[:, "geography"] = "changed"
    assert silver_mines.iloc[0]["feature_name"] == "Test Mine A"
    assert silver_statcan.iloc[0]["geography"] == "Ontario"


def test_gold_tables_contain_every_column_the_gemini_tools_query():
    dim, fact = build_gold_models(*_silver_pair())

    missing_dim = TOOL_DIM_COLUMNS - set(dim.columns)
    missing_fact = TOOL_FACT_COLUMNS - set(fact.columns)
    assert not missing_dim, f"dim_mine_feature is missing {sorted(missing_dim)}"
    assert not missing_fact, f"fact_mineral_production_monthly is missing {sorted(missing_fact)}"
