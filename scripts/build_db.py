"""Build data/minemind.duckdb from the committed Gold Parquet files.

Runs during the Docker build. It uses the same get_duckdb_connection() as the pipeline,
then fails loudly if any Gold view is missing or empty.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from src.database.duckdb_manager import get_duckdb_connection  # noqa: E402

PARQUET = ["dim_mine_feature", "fact_mineral_production_monthly", "source_manifest", "etl_run_log"]
missing = [n for n in PARQUET if not (ROOT / "data/processed/gold" / f"{n}.parquet").exists()]
if missing:
    sys.exit(f"Missing Gold Parquet files: {missing}. Commit them: git add data/processed/gold")

con = get_duckdb_connection()
for name in PARQUET:
    count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    if count == 0:
        sys.exit(f"{name} is empty")
    print(f"{name}: {count} rows")
con.close()
print("DuckDB ready.")
