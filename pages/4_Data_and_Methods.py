import pandas as pd
import streamlit as st

from src.database.duckdb_manager import get_duckdb_connection
from src.ui.theme import inject_css

st.set_page_config(page_title="MineMind | Data & Methods", page_icon="📚", layout="wide")
inject_css()


@st.cache_data(ttl=600)
def run(sql: str) -> pd.DataFrame:
    con = get_duckdb_connection(read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


st.title("Data & Methods")
st.warning("Independent prototype - not a government product. Check the original sources before relying on any figure.")

st.subheader("Sources and licences")
try:
    st.dataframe(run("SELECT * FROM source_manifest ORDER BY 1"), use_container_width=True, hide_index=True)
except Exception as error:
    st.error(f"Unable to load the source manifest: {error}")
st.markdown(
    "- Contains information licensed under the **Open Government Licence - Canada** "
    "(Natural Resources Canada, Map 900A).\n"
    "- Source: **Statistics Canada**, Table 16-10-0019-01, used under the "
    "[Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence). "
    "This is not the official version of the data."
)

st.subheader("Pipeline")
st.markdown(
    "**Bronze** raw files kept unchanged with a checksum manifest -> **Silver** cleaned and standardized, "
    "rejected rows logged -> **Gold** `dim_mine_feature` and `fact_mineral_production_monthly` "
    "-> **DuckDB** views over Parquet -> Streamlit pages and Gemini tools (read-only, parameterized queries)."
)
try:
    st.caption("Latest pipeline log entries")
    st.dataframe(run("SELECT * FROM etl_run_log").tail(10), use_container_width=True, hide_index=True)
except Exception as error:
    st.info(f"Pipeline log not available: {error}")

st.subheader("Data coverage")
try:
    cov = run("""SELECT
        (SELECT count(*) FROM dim_mine_feature) AS mine_features,
        (SELECT count(*) FROM fact_mineral_production_monthly) AS production_observations,
        (SELECT count(*) FROM fact_mineral_production_monthly WHERE value IS NULL) AS missing_or_suppressed,
        (SELECT count(*) FROM fact_mineral_production_monthly WHERE value = 0) AS reported_zero,
        (SELECT min(reference_month) FROM fact_mineral_production_monthly) AS first_month,
        (SELECT max(reference_month) FROM fact_mineral_production_monthly) AS latest_month""")
    st.dataframe(cov, use_container_width=True, hide_index=True)
    st.caption("Missing values are `..` (not available) or `x` (suppressed for confidentiality). "
               "They are kept as missing and are never treated as zero. A real reported 0 stays 0.")
    units = run("""SELECT measure, unit, count(*) AS observations FROM fact_mineral_production_monthly
                   GROUP BY 1, 2 ORDER BY 1, 2""")
    st.dataframe(units, use_container_width=True, hide_index=True)
except Exception as error:
    st.error(f"Unable to compute coverage: {error}")

st.subheader("How to read the numbers")
st.markdown(
    "- **Series.** Statistics Canada publishes separate series per product basis, for example "
    "*Nickel, concentrates (kilograms)* and *Nickel, recoverable (kilograms)*. They measure different things "
    "and are **never added together**. Each chart and each AI answer names the exact series, unit and vector ID.\n"
    "- **Units differ** by commodity (kilograms, grams, metric tonnes, dollars). Values are shown as reported; "
    "conversions to tonnes are computed in Python, not by the AI.\n"
    "- **Provincial, not mine-level.** Statistics Canada values describe a province or region. "
    "They are never attributed to an individual mine, and the two datasets are not joined by mine.\n"
    "- **Mine map.** NRCan Map 900A shows significant mapped features only, not every mine. "
    "The commodity shown is the first one listed in the source record.\n"
    "- **Revisions.** Recent months can be revised by Statistics Canada."
)

st.subheader("Responsible AI")
st.markdown(
    "- Gemini can only call three allow-listed, read-only tools with validated, parameterized inputs. "
    "It never writes SQL or runs code.\n"
    "- Counts, totals, averages and unit conversions are computed in Python/SQL and returned to Gemini.\n"
    "- Every answer shows the tools called and the datasets used. If no tool was called, the page says so.\n"
    "- The app makes no claims about pollution, health risk or mine safety."
)
