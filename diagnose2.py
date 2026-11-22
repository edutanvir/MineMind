"""diagnose2.py - read-only. Run from the project root:  python diagnose2.py
Finds out why Ontario Nickel has two 'Quantity produced' rows per month. Paste the whole output back."""
import duckdb
import pandas as pd

DB = "data/minemind.duckdb"
CSV = "data/raw/statcan/16100019.csv"
FACT = "fact_mineral_production_monthly"


def sql_part():
    con = duckdb.connect(DB, read_only=True)

    def show(title, sql):
        print(f"\n=== {title}")
        try:
            print(con.execute(sql).df().to_string(index=False))
        except Exception as e:
            print("ERROR:", e)

    show("Ontario nickel 2026-09, every row", f"""SELECT measure, commodity_raw, vector, value, unit, status_symbol
        FROM {FACT} WHERE geography = 'Ontario' AND commodity = 'Nickel' AND reference_month = '2026-09'
        ORDER BY measure, commodity_raw""")
    show("raw product names behind commodity 'Nickel' and 'Copper'", f"""SELECT commodity, commodity_raw, count(*) AS n
        FROM {FACT} WHERE commodity IN ('Nickel', 'Copper') GROUP BY 1, 2 ORDER BY 1, 2""")
    show("how many (month, geography, commodity, measure) keys are duplicated", f"""SELECT count(*) AS duplicated_keys FROM (
        SELECT reference_month, geography, commodity, measure FROM {FACT}
        GROUP BY 1, 2, 3, 4 HAVING count(*) > 1)""")
    show("which commodities are affected", f"""SELECT commodity, count(*) AS duplicated_keys FROM (
        SELECT reference_month, geography, commodity, measure FROM {FACT}
        GROUP BY 1, 2, 3, 4 HAVING count(*) > 1) GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    con.close()


def raw_part():
    print("\n=== raw StatCan CSV")
    raw = pd.read_csv(CSV, encoding="utf-8-sig", dtype=str)
    for word in ("nickel", "copper"):
        names = sorted(raw["Products"][raw["Products"].str.contains(word, case=False, na=False)].unique())
        print(f"\nProducts containing '{word}':", names)
    sub = raw[raw["GEO"].str.contains("Ontario", na=False) & (raw["REF_DATE"] == "2026-09")
              & raw["Products"].str.contains("nickel", case=False, na=False)]
    print("\nOntario, 2026-09, nickel rows in the raw file:")
    print(sub[["Products", "Variables", "UOM", "VALUE", "STATUS", "SYMBOL"]].to_string(index=False))
    num = pd.to_numeric(raw["VALUE"], errors="coerce")
    print("\nraw VALUE counts -> blank:", int(num.isna().sum()), " zero:", int((num == 0).sum()),
          " positive:", int((num > 0).sum()))
    print("\nraw STATUS/SYMBOL combinations:")
    print(raw.groupby(["STATUS", "SYMBOL"], dropna=False).size().reset_index(name="n").to_string(index=False))


if __name__ == "__main__":
    try:
        sql_part()
    except Exception as e:
        print("SQL part failed:", e)
    try:
        raw_part()
    except Exception as e:
        print("Raw part failed:", e)
