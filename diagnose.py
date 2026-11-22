"""diagnose.py - read-only check of your Gold data. Run from the project root:  python diagnose.py
Prints counts, valid values and units. Safe to paste the whole output back (no secrets)."""
import duckdb
import pandas as pd

DB = "data/minemind.duckdb"
CSV = "data/raw/statcan/16100019.csv"


def show(title, sql, con):
    print(f"\n=== {title}")
    try:
        print(con.execute(sql).df().to_string(index=False))
    except Exception as e:  # keep going so one failure doesn't hide the rest
        print("ERROR:", e)


con = duckdb.connect(DB, read_only=True)
show("tables and views", "SELECT table_name, table_type FROM information_schema.tables ORDER BY 1", con)
show("row counts", """SELECT
  (SELECT count(*) FROM dim_mine_feature) AS mines,
  (SELECT count(*) FROM dim_mine_feature WHERE province_abr = 'ON') AS ontario_mines,
  (SELECT count(*) FROM dim_mine_feature WHERE latitude IS NULL OR longitude IS NULL) AS mines_no_coords,
  (SELECT count(*) FROM fact_mineral_production_monthly) AS fact_rows,
  (SELECT count(*) FROM fact_mineral_production_monthly WHERE value IS NULL) AS fact_null_values,
  (SELECT count(*) FROM fact_mineral_production_monthly WHERE value = 0) AS fact_zero_values""", con)
show("province_abr values", "SELECT province_abr, count(*) AS n FROM dim_mine_feature GROUP BY 1 ORDER BY 2 DESC", con)
show("top commodity_raw", "SELECT commodity_raw, count(*) AS n FROM dim_mine_feature GROUP BY 1 ORDER BY 2 DESC LIMIT 15", con)
show("geographies", "SELECT DISTINCT geography FROM fact_mineral_production_monthly ORDER BY 1", con)
show("commodities", "SELECT DISTINCT commodity FROM fact_mineral_production_monthly ORDER BY 1", con)
show("measure + unit", "SELECT measure, unit, count(*) AS n FROM fact_mineral_production_monthly GROUP BY 1, 2 ORDER BY 1, 2", con)
show("month range", "SELECT min(reference_month) AS first_month, max(reference_month) AS last_month FROM fact_mineral_production_monthly", con)
show("last 6 Ontario nickel rows", """SELECT reference_month, geography, commodity, measure, value, unit, status_symbol
  FROM fact_mineral_production_monthly
  WHERE lower(geography) LIKE '%ontario%' AND lower(commodity) LIKE '%nickel%'
  ORDER BY reference_month DESC, measure LIMIT 6""", con)
con.close()

print("\n=== raw StatCan CSV")
try:
    raw = pd.read_csv(CSV, encoding="utf-8-sig", dtype=str)
    print("columns:", list(raw.columns))
    cols = [c for c in ("UOM", "SCALAR_FACTOR") if c in raw.columns]
    if cols:
        print(raw.groupby(cols, dropna=False).size().reset_index(name="n").to_string(index=False))
    else:
        print("UOM / SCALAR_FACTOR columns not found")
except Exception as e:
    print("ERROR:", e)
