"""
MineMind: Central configuration module.

All project file paths and schema constants live here.
Every other module imports from this file instead of hardcoding paths.

Path strategy:
  PROJECT_ROOT is derived from the location of *this file* (src/config.py),
  so paths resolve correctly regardless of where Python is started from.
  Using Path(__file__).resolve().parent.parent means:
    __file__  → .../MineMind/src/config.py
    .parent   → .../MineMind/src/
    .parent   → .../MineMind/          ← PROJECT_ROOT
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root — always the MineMind/ directory, regardless of CWD
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Raw (Bronze) data directories — never written to by the pipeline
# ---------------------------------------------------------------------------
RAW_DIR:          Path = PROJECT_ROOT / "data" / "raw"
RAW_NRCAN_DIR:    Path = RAW_DIR / "nrcan_900a"
RAW_STATCAN_DIR:  Path = RAW_DIR / "statcan"

# NRCan 900A source files
NRCAN_GDB_PATH:   Path = RAW_NRCAN_DIR / "900A.gdb"
NRCAN_ZIP_PATH:   Path = RAW_NRCAN_DIR / "900A.gdb.zip"

# Statistics Canada source files
STATCAN_CSV_PATH:      Path = RAW_STATCAN_DIR / "16100019.csv"
STATCAN_ALT_CSV_PATH:  Path = RAW_STATCAN_DIR / "1610001901.csv"   # symlink
STATCAN_ZIP_PATH:      Path = RAW_STATCAN_DIR / "16100019-eng.zip"
STATCAN_META_PATH:     Path = RAW_STATCAN_DIR / "1610001901_MetaData.csv"

# ---------------------------------------------------------------------------
# Processed data directories
# ---------------------------------------------------------------------------
PROCESSED_DIR:    Path = PROJECT_ROOT / "data" / "processed"
BRONZE_DIR:       Path = PROCESSED_DIR / "bronze"   # reserved for future use
SILVER_DIR:       Path = PROCESSED_DIR / "silver"
GOLD_DIR:         Path = PROCESSED_DIR / "gold"

# Silver Parquet files
SILVER_MINES_PATH:          Path = SILVER_DIR / "silver_mines.parquet"
SILVER_STATCAN_PATH:        Path = SILVER_DIR / "silver_statcan_production.parquet"

# Gold Parquet files
GOLD_MINES_PATH:            Path = GOLD_DIR / "dim_mine_feature.parquet"
GOLD_PRODUCTION_PATH:       Path = GOLD_DIR / "fact_mineral_production_monthly.parquet"
GOLD_MANIFEST_PATH:         Path = GOLD_DIR / "source_manifest.parquet"
GOLD_RUN_LOG_PATH:          Path = GOLD_DIR / "etl_run_log.parquet"

# ---------------------------------------------------------------------------
# DuckDB database
# ---------------------------------------------------------------------------
DUCKDB_PATH: Path = PROJECT_ROOT / "data" / "minemind.duckdb"

# ---------------------------------------------------------------------------
# Documentation and logs
# ---------------------------------------------------------------------------
DOCS_DIR: Path = PROJECT_ROOT / "docs"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
SOURCE_INSPECTION_DOC: Path = DOCS_DIR / "source_inspection.md"

# ---------------------------------------------------------------------------
# NRCan 900A GDB layer names
# ---------------------------------------------------------------------------
NRCAN_LAYER_PRODUCING_MINES: str = "ProducingMines"
NRCAN_LAYER_METALWORKS:      str = "MetalWorks"
NRCAN_LAYER_TOP100EXP:       str = "Top100Exp"
NRCAN_LAYERS_TO_LOAD: list[str] = [
    NRCAN_LAYER_PRODUCING_MINES,
    NRCAN_LAYER_METALWORKS,
    NRCAN_LAYER_TOP100EXP,
]

# NRCan native coordinate reference system (Canada Atlas Lambert)
NRCAN_NATIVE_CRS: str = "EPSG:3978"

# ---------------------------------------------------------------------------
# SCHEMA_MAP
#
# Every entry is derived directly from docs/source_inspection.md and the
# terminal output captured on 2026-11-21.  Source field names are the actual
# column names read off the live files.  Internal names are the names used
# inside Silver/Gold tables.
#
# Columns that are DROPPED are listed with internal_name=None and a reason.
# No source field is silently omitted.
# ---------------------------------------------------------------------------

#
# NRCan Map 900A — ProducingMines layer ONLY
# Source shape: (183, 24)  |  Source CRS: EPSG:3978
# Source columns verified from docs/source_inspection.md, 2026-11-21
#
# IMPORTANT: This schema map applies strictly to the 'ProducingMines' layer.
# Other 900A layers in the geodatabase (such as 'MetalWorks' with 18 columns,
# and 'Top100Exp' with 9 columns) have distinct schemas documented in
# docs/source_inspection.md and have not yet been fully inspected or mapped.
#
NRCAN_SCHEMA_MAP: list[dict] = [
    # --- Identifier ---
    {"source": "count",                   "internal": "source_feature_id",    "keep": True,  "note": "Row sequence number; becomes feature_key prefix"},

    # --- Mine operation ---
    {"source": "operation_name_en",       "internal": "feature_name",         "keep": True,  "note": "English operation name"},
    {"source": "operation_group_en",      "internal": "feature_type",         "keep": True,  "note": "English operation category (e.g. Metal mines)"},
    {"source": "operation_name_fr",       "internal": None,                   "keep": False, "note": "Dropped: French duplicate; English retained"},
    {"source": "operation_group_fr",      "internal": None,                   "keep": False, "note": "Dropped: French duplicate"},
    {"source": "operation_nb",            "internal": None,                   "keep": False, "note": "Dropped: internal numeric code, no analytical use"},

    # --- Province ---
    {"source": "province_abr",            "internal": "province_abr",         "keep": True,  "note": "Province/territory abbreviation as provided in source (preserves original source values, including 2-to-3 character historical codes such as NFL, NWT, ON)"},
    {"source": "province_en",             "internal": "province",             "keep": True,  "note": "English province full name"},
    {"source": "province_fr",             "internal": None,                   "keep": False, "note": "Dropped: French duplicate"},
    {"source": "province_nb",             "internal": None,                   "keep": False, "note": "Dropped: internal numeric code, no analytical use"},

    # --- Operator ---
    {"source": "operator_owners_en",      "internal": "operator_name",        "keep": True,  "note": "English operator / owner name"},
    {"source": "operator_owners_fr",      "internal": None,                   "keep": False, "note": "Dropped: French duplicate"},

    # --- Facility ---
    {"source": "facilities_code_en_spelt","internal": "facilities_type",      "keep": True,  "note": "English facility type (e.g. Open-pit, concentrator)"},
    {"source": "facilities_code_fr_spelt","internal": None,                   "keep": False, "note": "Dropped: French duplicate"},

    # --- Location ---
    {"source": "city_en",                 "internal": "city",                 "keep": True,  "note": "Nearest city / municipality (English)"},
    {"source": "city_fr",                 "internal": None,                   "keep": False, "note": "Dropped: French duplicate"},

    # --- Commodity ---
    {"source": "product_group_en_spelt",  "internal": "commodity_group_raw",  "keep": True,  "note": "High-level commodity family (e.g. Precious metals, Base metals). AUDIT NOTE: was dropped in v0.1 — to be retained from Task 3 onwards."},
    {"source": "product_en_spelt",        "internal": "commodity_raw",        "keep": True,  "note": "Specific commodity or combination (e.g. 'Gold', 'Nickel, copper, cobalt')"},
    {"source": "product_group_fr_spelt",  "internal": None,                   "keep": False, "note": "Dropped: French duplicate"},
    {"source": "product_fr_spelt",        "internal": None,                   "keep": False, "note": "Dropped: French duplicate"},

    # --- Geography ---
    {"source": "latitude",                "internal": "latitude",             "keep": True,  "note": "WGS84 decimal latitude (source includes pre-computed lat/lon)"},
    {"source": "longitude",               "internal": "longitude",            "keep": True,  "note": "WGS84 decimal longitude"},
    {"source": "website",                 "internal": "website",              "keep": True,  "note": "Official operation or company URL"},
    {"source": "geometry",                "internal": None,                   "keep": False, "note": "Preserved in raw Bronze GDB source (projected EPSG:3978 Point); omitted from tabular Parquet where WGS84 latitude/longitude columns are used for web mapping and analytical queries"},
]

#
# Statistics Canada Table 16-10-0019-01
# Source shape: (172346, 16)  |  Tidy long-format monthly time series
# Source columns verified from docs/source_inspection.md, 2026-11-21
# Release date: 2026-11-20
#
STATCAN_SCHEMA_MAP: list[dict] = [
    # --- Time ---
    {"source": "REF_DATE",        "internal": "reference_month",  "keep": True,  "note": "Reference period in YYYY-MM format"},

    # --- Geography ---
    {"source": "GEO",             "internal": "geography",        "keep": True,  "note": "Geographic name (e.g. 'Ontario', 'Canada')"},
    {"source": "DGUID",           "internal": "dguid",            "keep": True,  "note": "Statistics Canada geography identifier. AUDIT NOTE: was dropped in v0.1 — to be retained from Task 3 onwards."},

    # --- Commodity / measure ---
    {"source": "Products",        "internal": "commodity_raw",    "keep": True,  "note": "Mineral product label including unit in parentheses (e.g. 'Gold recoverable (kilograms)')"},
    {"source": "Variables",       "internal": "measure",          "keep": True,  "note": "Statistical measure: Quantity produced | Quantity shipped | Value of shipments | Closing inventories"},

    # --- Units ---
    {"source": "UOM",             "internal": "unit",             "keep": True,  "note": "Unit of measure string (e.g. 'Kilograms', 'Metric tonnes', 'Dollars')"},
    {"source": "UOM_ID",          "internal": None,               "keep": False, "note": "Dropped: numeric UOM code; human-readable UOM retained"},

    # --- Scale ---
    {"source": "SCALAR_FACTOR",   "internal": None,               "keep": False, "note": "Audited: 100% constant across all 172,346 rows ('units', multiplier 10^0=1); dropped as redundant with UOM, with zero scale adjustment needed"},
    {"source": "SCALAR_ID",       "internal": None,               "keep": False, "note": "Audited: 100% constant across all 172,346 rows ('0'); dropped as redundant scalar index"},

    # --- Series identifiers ---
    {"source": "VECTOR",          "internal": "vector",           "keep": True,  "note": "StatCan time-series vector ID (e.g. v1146004294); useful for direct API access"},
    {"source": "COORDINATE",      "internal": "coordinate",       "keep": True,  "note": "Cube coordinate index (e.g. 1.1.1); part of StatCan data model"},

    # --- Value and quality flags ---
    {"source": "VALUE",           "internal": "value",            "keep": True,  "note": "Numeric observation; suppressed or unavailable values stored as NaN (never zero)"},
    {"source": "STATUS",          "internal": "status_symbol",    "keep": True,  "note": "Data quality flag: empty=valid, 'x'=confidential, '..'=not available"},
    {"source": "SYMBOL",          "internal": "symbol",           "keep": True,  "note": "Footnote / revision marker"},
    {"source": "TERMINATED",      "internal": "terminated",       "keep": True,  "note": "Discontinued series flag. AUDIT NOTE: was dropped in v0.1 — to be retained from Task 3 onwards."},
    {"source": "DECIMALS",        "internal": None,               "keep": False, "note": "Dropped: precision hint; all values stored as float64 in Parquet"},
]


# ---------------------------------------------------------------------------
# Convenience lookups derived from the schema maps above
# ---------------------------------------------------------------------------

def _build_rename_map(schema: list[dict]) -> dict[str, str]:
    """Return {source_col: internal_col} for all kept columns with an internal name."""
    return {
        entry["source"]: entry["internal"]
        for entry in schema
        if entry["keep"] and entry["internal"] is not None
    }

def _build_keep_sources(schema: list[dict]) -> list[str]:
    """Return list of source column names that are retained (kept=True)."""
    return [entry["source"] for entry in schema if entry["keep"]]


NRCAN_RENAME_MAP:    dict[str, str] = _build_rename_map(NRCAN_SCHEMA_MAP)
NRCAN_KEEP_SOURCES:  list[str]      = _build_keep_sources(NRCAN_SCHEMA_MAP)

STATCAN_RENAME_MAP:  dict[str, str] = _build_rename_map(STATCAN_SCHEMA_MAP)
STATCAN_KEEP_SOURCES: list[str]     = _build_keep_sources(STATCAN_SCHEMA_MAP)
