
import re
from datetime import datetime, timezone

import pandas as pd
import geopandas as gpd


COMMODITY_MAPPING = {
    "gold": "Gold",
    "nickel": "Nickel",
    "copper": "Copper",
    "cobalt": "Cobalt",
    "zinc": "Zinc",
    "silver": "Silver",
    "lead": "Lead",
    "iron": "Iron Ore",
    "platinum": "Platinum Group Metals",
    "palladium": "Platinum Group Metals",
    "uranium": "Uranium",
    "lithium": "Lithium",
    "molybdenum": "Molybdenum",
    "niobium": "Niobium",
    "diamond": "Diamonds",
    "salt": "Salt",
}


def extract_primary_commodity(product_str: str) -> str:
    """Normalize commodity text into a standardized commodity family."""
    if not product_str or not isinstance(product_str, str):
        return "Other"

    low = product_str.lower()

    for key, val in COMMODITY_MAPPING.items():
        if key in low:
            return val

    return product_str.split(",")[0].strip()


def process_nrcan_silver(raw_layers: dict) -> tuple[pd.DataFrame, dict]:
    """Clean and standardize NRCan 900A producing mines into Silver layer."""
    gdf = raw_layers.get("ProducingMines")

    if gdf is None:
        raise ValueError("ProducingMines layer missing from NRCan dataset")

    total_input = len(gdf)
    rejections = []

    # Copy to avoid mutating raw input.
    df = gdf.copy()

    # Verify geometry and coordinates.
    invalid_coords = (
        df["latitude"].isna()
        | df["longitude"].isna()
        | (df["latitude"] < 40.0)
        | (df["latitude"] > 85.0)
        | (df["longitude"] < -145.0)
        | (df["longitude"] > -50.0)
    )

    if invalid_coords.any():
        rejected_count = int(invalid_coords.sum())
        rejections.append(
            f"{rejected_count} rows with invalid/out-of-bound coordinates"
        )
        df = df[~invalid_coords]

    # Standardize column mappings.
    df["feature_key"] = df["count"].apply(lambda x: f"MINE_{int(x):04d}")
    df["source_feature_id"] = df["count"].astype(int)
    df["feature_name"] = df["operation_name_en"].str.strip()
    df["operator_name"] = df["operator_owners_en"].str.strip()
    df["province"] = df["province_en"].str.strip()
    df["province_abr"] = df["province_abr"].str.strip().str.upper()
    df["city"] = df["city_en"].str.strip()
    df["feature_type"] = df["operation_group_en"].str.strip()
    df["commodity_raw"] = df["product_en_spelt"].str.strip()
    df["commodity_normalized"] = df["commodity_raw"].apply(
        extract_primary_commodity
    )
    df["facilities_type"] = df["facilities_code_en_spelt"].str.strip()
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    df["website"] = df["website"].str.strip()
    df["source_layer"] = "ProducingMines"
    df["source_vintage"] = "NRCan Map 900A (2024)"

    selected_cols = [
        "feature_key",
        "source_feature_id",
        "feature_name",
        "operator_name",
        "province",
        "province_abr",
        "city",
        "feature_type",
        "commodity_raw",
        "commodity_normalized",
        "facilities_type",
        "latitude",
        "longitude",
        "website",
        "source_layer",
        "source_vintage",
    ]

    silver_mines = df[selected_cols].copy()

    meta = {
        "input_rows": total_input,
        "output_rows": len(silver_mines),
        "rejected_rows": total_input - len(silver_mines),
        "rejection_reasons": "; ".join(rejections) if rejections else "None",
    }

    return silver_mines, meta


def process_statcan_silver(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean and standardize Statistics Canada table 16-10-0019-01 into Silver layer."""
    total_input = len(raw_df)
    rejections = []

    df = raw_df.copy()

    # Validate reference dates (YYYY-MM).
    # Accept only months 01 through 12.
    valid_dates = df["REF_DATE"].str.match(
        r"^\d{4}-(?:0[1-9]|1[0-2])$"
    )

    if not valid_dates.all():
        bad_dates = int((~valid_dates).sum())
        rejections.append(
            f"{bad_dates} rows with invalid REF_DATE format"
        )
        df = df[valid_dates]

    # Parse numeric VALUE carefully.
    # Never convert suppressed or missing values to zero.
    df["numeric_value"] = pd.to_numeric(
        df["VALUE"].str.replace(",", "", regex=False),
        errors="coerce",
    )

    # Standardize column mappings.
    df["reference_month"] = df["REF_DATE"].str.strip()
    df["geography"] = df["GEO"].str.strip()
    df["commodity_raw"] = df["Products"].str.strip()
    df["commodity"] = df["commodity_raw"].apply(extract_primary_commodity)
    df["measure"] = df["Variables"].str.strip()
    df["value"] = df["numeric_value"]
    df["unit"] = df["UOM"].str.strip()
    df["status_symbol"] = df["STATUS"].str.strip()
    df["symbol"] = df["SYMBOL"].str.strip()
    df["vector"] = df["VECTOR"].str.strip()
    df["coordinate"] = df["COORDINATE"].str.strip()
    df["source_table"] = "16-10-0019-01"
    df["retrieval_date"] = "2026-11-21"

    selected_cols = [
        "reference_month",
        "geography",
        "commodity",
        "commodity_raw",
        "measure",
        "value",
        "unit",
        "status_symbol",
        "symbol",
        "vector",
        "coordinate",
        "source_table",
        "retrieval_date",
    ]

    silver_statcan = df[selected_cols].copy()

    meta = {
        "input_rows": total_input,
        "output_rows": len(silver_statcan),
        "rejected_rows": total_input - len(silver_statcan),
        "rejection_reasons": "; ".join(rejections) if rejections else "None",
    }

    return silver_statcan, meta


def build_gold_models(
    silver_mines: pd.DataFrame,
    silver_statcan: pd.DataFrame,
):
    """Build Gold analytical dimension and fact tables."""
    # dim_mine_feature
    dim_mine_feature = silver_mines.copy()

    # fact_mineral_production_monthly
    fact_mineral_production_monthly = silver_statcan.copy()

    return dim_mine_feature, fact_mineral_production_monthly
