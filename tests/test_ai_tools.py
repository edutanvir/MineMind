
import duckdb
import pytest

from src.ai import tools


@pytest.fixture
def production_db(tmp_path, monkeypatch):
    """Create an isolated DuckDB database for production-tool tests."""
    db_path = str(tmp_path / "test_minemind.duckdb")
    monkeypatch.setattr(tools, "DB_PATH", db_path)

    with duckdb.connect(db_path) as con:
        con.execute("""
            CREATE TABLE fact_mineral_production_monthly (
                reference_month VARCHAR,
                geography VARCHAR,
                commodity VARCHAR,
                commodity_raw VARCHAR,
                measure VARCHAR,
                value DOUBLE,
                unit VARCHAR,
                status_symbol VARCHAR,
                symbol VARCHAR,
                vector VARCHAR,
                coordinate VARCHAR
            )
        """)

        # Two Nickel series, with different units and identifiers.
        for month_number in range(1, 41):
            month = f"2023-{month_number:02d}" if month_number <= 12 else (
                f"{2023 + (month_number - 1) // 12}-"
                f"{(month_number - 1) % 12 + 1:02d}"
            )

            con.execute("""
                INSERT INTO fact_mineral_production_monthly
                VALUES (?, 'Ontario', 'Nickel',
                        'Nickel, concentrates (kilograms)',
                        'Quantity produced', ?, 'kilograms',
                        '', '', 'v100', '8.43.1')
            """, [month, float(month_number)])

            con.execute("""
                INSERT INTO fact_mineral_production_monthly
                VALUES (?, 'Ontario', 'Nickel',
                        'Nickel, refined (dollars)',
                        'Quantity produced', ?, 'dollars',
                        '', '', 'v200', '8.44.1')
            """, [month, float(month_number * 100)])

        # Suppressed observation: value must remain NULL.
        con.execute("""
            INSERT INTO fact_mineral_production_monthly
            VALUES (
                '2026-05', 'Ontario', 'Nickel',
                'Nickel, concentrates (kilograms)',
                'Quantity produced', NULL, 'kilograms',
                'x', '', 'v100', '8.43.1'
            )
        """)

    yield db_path

    tools._distinct.cache_clear()


def test_ambiguous_series_requires_selection(production_db):
    result = tools.get_production_trend(
        "Ontario", "Nickel", "Quantity produced"
    )

    assert result["requires_series"] is True
    assert result["rows"] == []
    assert len(result["available_series"]) == 2


def test_specific_series_returns_only_selected_series(production_db):
    result = tools.get_production_trend(
        "Ontario",
        "Nickel",
        "Quantity produced",
        series="Nickel, concentrates (kilograms)",
        unit="kilograms",
    )

    assert result["series"] == "Nickel, concentrates (kilograms)"
    assert result["unit"] == "kilograms"
    assert all(
        row["series"] == "Nickel, concentrates (kilograms)"
        for row in result["rows"]
    )
    assert all(row["unit"] == "kilograms" for row in result["rows"])


def test_returns_latest_36_distinct_months(production_db):
    result = tools.get_production_trend(
        "Ontario",
        "Nickel",
        "Quantity produced",
        last_n_months=36,
        series="Nickel, concentrates (kilograms)",
        unit="kilograms",
    )

    assert result["months_requested"] == 36
    assert result["months_returned"] == 36
    assert len({row["month"] for row in result["rows"]}) == 36


def test_suppressed_values_remain_null(production_db):
    result = tools.get_production_trend(
        "Ontario",
        "Nickel",
        "Quantity produced",
        series="Nickel, concentrates (kilograms)",
        unit="kilograms",
        start_month="2026-05",
        end_month="2026-05",
    )

    assert len(result["rows"]) == 1
    assert result["rows"][0]["value"] is None
    assert result["rows"][0]["status_symbol"] == "x"


def test_invalid_series_returns_available_choices(production_db):
    result = tools.get_production_trend(
        "Ontario",
        "Nickel",
        "Quantity produced",
        series="Nickel, imaginary series",
    )

    assert "error" in result
    assert result["rows"] == []
    assert len(result["available_series"]) == 2


def test_month_count_is_capped_at_240(production_db):
    result = tools.get_production_trend(
        "Ontario",
        "Nickel",
        "Quantity produced",
        last_n_months=999,
        series="Nickel, concentrates (kilograms)",
        unit="kilograms",
    )

    assert result["months_requested"] == 240
    assert result["months_returned"] <= 240
