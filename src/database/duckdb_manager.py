"""
MineMind: DuckDB connection manager.

Creates a DuckDB connection and registers views that point to the Gold
Parquet files. All paths come from src/config.py so they are always
absolute — the views work correctly regardless of which directory the
Python process is started from.

Supports both read-only (using session-scoped TEMPORARY VIEWs) and
writable connections (using persistent VIEWs).
"""

from pathlib import Path
import duckdb

from src.config import (
    DUCKDB_PATH,
    GOLD_MINES_PATH,
    GOLD_PRODUCTION_PATH,
    GOLD_MANIFEST_PATH,
    GOLD_RUN_LOG_PATH,
)


def get_duckdb_connection(
    db_path: Path = DUCKDB_PATH,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with views pointing to Gold Parquet files.

    Views are created with absolute paths so they resolve correctly
    regardless of the current working directory.

    For read-only connections (read_only=True), session-scoped TEMPORARY VIEWs
    are registered to prevent catalog write errors on read-only databases.
    For writable connections (read_only=False), persistent VIEWs are created.

    Parameters
    ----------
    db_path : Path
        Location of the DuckDB database file. Defaults to the central
        path defined in src/config.py.
    read_only : bool
        Open the database in read-only mode. Use True in Streamlit
        pages and Gemini tools; False only during pipeline writes.
    """
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=read_only)

    # Register views using absolute path strings with single-quote escaping
    _register_view(con, "dim_mine_feature", GOLD_MINES_PATH, read_only=read_only)
    _register_view(con, "fact_mineral_production_monthly", GOLD_PRODUCTION_PATH, read_only=read_only)
    _register_view(con, "fact_mineral_production", GOLD_PRODUCTION_PATH, read_only=read_only)  # alias
    _register_view(con, "source_manifest", GOLD_MANIFEST_PATH, read_only=read_only)
    _register_view(con, "etl_run_log", GOLD_RUN_LOG_PATH, read_only=read_only)

    return con


def _register_view(
    con: duckdb.DuckDBPyConnection,
    view_name: str,
    parquet_path: Path,
    read_only: bool = False,
) -> None:
    """Create or replace a DuckDB view backed by a Parquet file.

    Skips registration silently if the Parquet file does not yet exist
    (e.g. before the pipeline has been run for the first time).
    Uses forward slashes in the SQL string and escapes apostrophes
    by doubling them (' -> '').
    """
    if not parquet_path.exists():
        return
    # Escape single quotes for SQL string literals and use forward slashes
    safe_path = parquet_path.as_posix().replace("'", "''")
    view_clause = "TEMPORARY VIEW" if read_only else "VIEW"
    con.execute(
        f"CREATE OR REPLACE {view_clause} {view_name} AS "
        f"SELECT * FROM read_parquet('{safe_path}')"
    )
