import uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from src.ingestion.load_nrcan import load_nrcan_raw
from src.ingestion.load_statcan import load_statcan_raw
from src.transformation.clean_data import (
    process_nrcan_silver,
    process_statcan_silver,
    build_gold_models,
)
from src.database.duckdb_manager import get_duckdb_connection

SILVER_DIR = Path("data/processed/silver")
GOLD_DIR = Path("data/processed/gold")

def run_pipeline():
    """Execute end-to-end Medallion pipeline: Bronze -> Silver -> Gold -> DuckDB."""
    run_id = f"RUN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    start_time = datetime.now(timezone.utc)
    code_version = "0.1.0"
    
    print("\n" + "=" * 60)
    print(f"MINEMIND PIPELINE EXECUTION: {run_id}")
    print("=" * 60)

    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    run_logs = []

    # ---------------------------------------------------------
    # 1. BRONZE & SILVER: NRCan Map 900A
    # ---------------------------------------------------------
    print("\n[1/4] Ingesting & processing NRCan Map 900A...")
    nrcan_start = datetime.now(timezone.utc)
    raw_nrcan, nrcan_checksum = load_nrcan_raw()
    silver_mines, nrcan_meta = process_nrcan_silver(raw_nrcan)
    
    silver_mines_path = SILVER_DIR / "silver_mines.parquet"
    silver_mines.to_parquet(silver_mines_path, index=False)
    print(f"  -> Saved Silver mines: {len(silver_mines)} records to {silver_mines_path}")

    run_logs.append({
        "run_id": run_id,
        "stage": "Silver_NRCan_Mines",
        "started_at": nrcan_start.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "input_rows": nrcan_meta["input_rows"],
        "output_rows": nrcan_meta["output_rows"],
        "rejected_rows": nrcan_meta["rejected_rows"],
        "rejection_reasons": nrcan_meta["rejection_reasons"],
        "code_version": code_version,
    })

    # ---------------------------------------------------------
    # 2. BRONZE & SILVER: Statistics Canada
    # ---------------------------------------------------------
    print("\n[2/4] Ingesting & processing Statistics Canada Table 16-10-0019-01...")
    statcan_start = datetime.now(timezone.utc)
    raw_statcan, statcan_checksum = load_statcan_raw()
    silver_statcan, statcan_meta = process_statcan_silver(raw_statcan)

    silver_statcan_path = SILVER_DIR / "silver_statcan_production.parquet"
    silver_statcan.to_parquet(silver_statcan_path, index=False)
    print(f"  -> Saved Silver StatCan: {len(silver_statcan)} records to {silver_statcan_path}")

    run_logs.append({
        "run_id": run_id,
        "stage": "Silver_StatCan_Production",
        "started_at": statcan_start.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "input_rows": statcan_meta["input_rows"],
        "output_rows": statcan_meta["output_rows"],
        "rejected_rows": statcan_meta["rejected_rows"],
        "rejection_reasons": statcan_meta["rejection_reasons"],
        "code_version": code_version,
    })

    # ---------------------------------------------------------
    # 3. GOLD MODELING
    # ---------------------------------------------------------
    print("\n[3/4] Building Gold analytical models...")
    gold_start = datetime.now(timezone.utc)
    dim_mine_feature, fact_mineral_production_monthly = build_gold_models(silver_mines, silver_statcan)

    dim_mine_path = GOLD_DIR / "dim_mine_feature.parquet"
    fact_prod_path = GOLD_DIR / "fact_mineral_production_monthly.parquet"

    dim_mine_feature.to_parquet(dim_mine_path, index=False)
    fact_mineral_production_monthly.to_parquet(fact_prod_path, index=False)

    print(f"  -> Saved Gold dim_mine_feature: {len(dim_mine_feature)} records")
    print(f"  -> Saved Gold fact_mineral_production_monthly: {len(fact_mineral_production_monthly)} records")

    # Source Manifest
    manifest_records = [
        {
            "source_id": "SRC_NRCAN_900A",
            "title": "Principal Mineral Areas, Producing Mines, and Oil and Gas Fields in Canada (Map 900A)",
            "publisher": "Natural Resources Canada (NRCan) / Geological Survey of Canada",
            "source_url": "https://ftp.maps.canada.ca/pub/nrcan_rncan/Mining-industry_Industrie-miniere/900A_and_top_100/900A.gdb.zip",
            "retrieved_at": "2026-11-21T20:44:00Z",
            "source_vintage": "Map 900A (2024)",
            "licence": "Open Government Licence - Canada",
            "file_name": "900A.gdb.zip",
            "checksum": nrcan_checksum,
        },
        {
            "source_id": "SRC_STATCAN_16_10_0019_01",
            "title": "Mineral production, monthly (Table 16-10-0019-01)",
            "publisher": "Statistics Canada",
            "source_url": "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610001901",
            "retrieved_at": "2026-11-21T20:53:00Z",
            "source_vintage": "Release 2026-11-20",
            "licence": "Statistics Canada Open Licence",
            "file_name": "16100019-eng.zip",
            "checksum": statcan_checksum,
        }
    ]
    manifest_df = pd.DataFrame(manifest_records)
    manifest_path = GOLD_DIR / "source_manifest.parquet"
    manifest_df.to_parquet(manifest_path, index=False)

    run_logs.append({
        "run_id": run_id,
        "stage": "Gold_Models",
        "started_at": gold_start.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "input_rows": len(silver_mines) + len(silver_statcan),
        "output_rows": len(dim_mine_feature) + len(fact_mineral_production_monthly),
        "rejected_rows": 0,
        "rejection_reasons": "None",
        "code_version": code_version,
    })

    # Save Run Logs
    run_log_df = pd.DataFrame(run_logs)
    run_log_path = GOLD_DIR / "etl_run_log.parquet"
    if run_log_path.exists():
        existing_logs = pd.read_parquet(run_log_path)
        run_log_df = pd.concat([existing_logs, run_log_df], ignore_index=True)
    run_log_df.to_parquet(run_log_path, index=False)

    # ---------------------------------------------------------
    # 4. DUCKDB INTEGRATION
    # ---------------------------------------------------------
    print("\n[4/4] Updating DuckDB views & verifying SQL engine...")
    con = get_duckdb_connection()
    mine_cnt = con.execute("SELECT count(*) FROM dim_mine_feature").fetchone()[0]
    prod_cnt = con.execute("SELECT count(*) FROM fact_mineral_production_monthly").fetchone()[0]
    ont_mine_cnt = con.execute("SELECT count(*) FROM dim_mine_feature WHERE province_abr = 'ON'").fetchone()[0]
    con.close()

    total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("MINEMIND PIPELINE RUN COMPLETE")
    print(f"Status: SUCCESS | Duration: {total_duration:.2f}s")
    print(f"Total Mapped Mines: {mine_cnt} (Ontario: {ont_mine_cnt})")
    print(f"Total StatCan Monthly Records: {prod_cnt}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    run_pipeline()
