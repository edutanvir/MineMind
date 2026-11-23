
import pandas as pd
import streamlit as st
import plotly.express as px

from src.database.duckdb_manager import get_duckdb_connection
from src.ui.theme import inject_css


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="MineMind | Production Analytics",
    page_icon="📊",
    layout="wide",
)

inject_css()


# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------

@st.cache_data(ttl=300)
def load_production_data():
    con = get_duckdb_connection(read_only=True)

    try:
        return con.execute("""
            SELECT *
            FROM fact_mineral_production_monthly
        """).df()
    finally:
        con.close()


try:
    production = load_production_data()
except Exception as error:
    st.error(f"Unable to load production data: {error}")
    st.stop()


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

st.title("Mineral Production Analytics")

st.markdown(
    "Explore monthly Canadian mineral production statistics "
    "using precisely identified Statistics Canada series."
)

st.divider()



# --------------------------------------------------
# FILTERS
# --------------------------------------------------

st.sidebar.header("Production Filters")

aggregate_geographies = {
    "Canada",
    "Atlantic region",
    "Prairies region",
}

province_options = sorted(
    set(production["geography"].dropna().unique())
    - aggregate_geographies
)

selected_province = st.sidebar.selectbox(
    "Province / Territory",
    province_options,
    key="production_province",
)

province_data = production[
    production["geography"] == selected_province
].copy()


# --------------------------------------------------
# STATISTICAL MEASURE
# --------------------------------------------------

measure_options = sorted(
    province_data.loc[
        province_data["value"].notna()
        & province_data["value"].gt(0),
        "measure",
    ].dropna().unique()
)

if not measure_options:
    st.warning(
        "No statistical measures with positive observations "
        "are available for this province."
    )
    st.stop()

selected_measure = st.sidebar.selectbox(
    "Statistical Measure",
    measure_options,
)

measure_data = province_data[
    province_data["measure"] == selected_measure
].copy()


# --------------------------------------------------
# COMMODITY — EXCLUDE ZERO-ONLY SERIES
# --------------------------------------------------

commodity_options = sorted(
    measure_data.loc[
        measure_data["value"].notna()
        & measure_data["value"].gt(0),
        "commodity",
    ].dropna().unique()
)

if not commodity_options:
    st.warning(
        "No commodities with positive observations are available "
        "for this province and measure."
    )
    st.stop()

selected_commodity = st.sidebar.selectbox(
    "Commodity",
    commodity_options,
)

commodity_data = measure_data[
    measure_data["commodity"] == selected_commodity
].copy()


# --------------------------------------------------
# UNIT
# --------------------------------------------------

unit_options = sorted(
    commodity_data.loc[
        commodity_data["value"].notna()
        & commodity_data["value"].gt(0),
        "unit",
    ].dropna().unique()
)

if not unit_options:
    st.warning(
        "No units with positive observations are available "
        "for this commodity."
    )
    st.stop()

selected_unit = st.sidebar.selectbox(
    "Unit",
    unit_options,
)

unit_data = commodity_data[
    commodity_data["unit"] == selected_unit
].copy()


# --------------------------------------------------
# EXACT STATISTICAL SERIES SELECTION
# --------------------------------------------------

series_columns = [
    "commodity_raw",
    "vector",
    "coordinate",
]

positive_series = unit_data[
    unit_data["value"].notna()
    & unit_data["value"].gt(0)
]

available_series = (
    positive_series[series_columns]
    .drop_duplicates()
    .sort_values(
        ["commodity_raw", "vector", "coordinate"],
        na_position="last",
    )
)

series_options = [
    (row.commodity_raw, row.vector, row.coordinate)
    for row in available_series.itertuples(index=False)
]


def format_series(series):
    commodity_raw, vector, coordinate = series

    return (
        f"{commodity_raw} | "
        f"Vector: {vector if pd.notna(vector) else 'N/A'} | "
        f"Coordinate: {coordinate if pd.notna(coordinate) else 'N/A'}"
    )


if not series_options:
    st.warning(
        "No exact statistical series with positive observations "
        "are available."
    )
    st.stop()

selected_series = st.sidebar.selectbox(
    "Exact Statistical Series",
    series_options,
    format_func=format_series,
)


# --------------------------------------------------
# FILTER USING EXACT SERIES IDENTIFIERS
# --------------------------------------------------

selected_raw, selected_vector, selected_coordinate = selected_series


def matches_value(series, selected_value):
    if pd.isna(selected_value):
        return series.isna()

    return series.eq(selected_value)


series_data = unit_data[
    matches_value(unit_data["commodity_raw"], selected_raw)
    & matches_value(unit_data["vector"], selected_vector)
    & matches_value(unit_data["coordinate"], selected_coordinate)
].copy()


# --------------------------------------------------
# DATE RANGE
# --------------------------------------------------

month_options = sorted(
    series_data["reference_month"].dropna().unique()
)

if not month_options:
    st.warning("No monthly observations are available for this series.")
    st.stop()

selected_months = st.sidebar.select_slider(
    "Date Range",
    options=month_options,
    value=(month_options[0], month_options[-1]),
)

filtered_data = series_data[
    series_data["reference_month"].between(
        selected_months[0],
        selected_months[1],
    )
].copy()

filtered_data = filtered_data.sort_values("reference_month")


# --------------------------------------------------
# SERIES INFORMATION
# --------------------------------------------------

st.subheader("Selected Statistical Series")

st.caption(
    f"Geography: {selected_province} | "
    f"Commodity: {selected_commodity} | "
    f"Measure: {selected_measure} | "
    f"Unit: {selected_unit}"
)

st.info(
    "This chart represents one exact Statistics Canada statistical "
    "series. Provincial production observations are not attributed "
    "to individual mines."
)

if selected_unit == "Dollars" and selected_measure != "Value of shipments":
    st.warning(
        "This is a monetary-valued statistical series, not a physical "
        "production quantity. Interpret the values accordingly."
    )


# --------------------------------------------------
# DATA QUALITY CHECK
# --------------------------------------------------

duplicate_months = filtered_data[
    filtered_data.duplicated(
        subset=["reference_month"],
        keep=False,
    )
]

if not duplicate_months.empty:
    st.error(
        "Multiple observations exist for the same month in this "
        "selected series. The chart has been stopped to prevent "
        "accidental aggregation."
    )
    st.dataframe(duplicate_months, use_container_width=True)
    st.stop()


# --------------------------------------------------
# KPI METRICS
# --------------------------------------------------

total_observations = len(filtered_data)
available_values = filtered_data["value"].count()
suppressed_values = filtered_data["value"].isna().sum()

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Observations",
    f"{total_observations:,}",
)

col2.metric(
    "Available Values",
    f"{available_values:,}",
)

col3.metric(
    "Missing / Suppressed Values",
    f"{suppressed_values:,}",
)


st.divider()


# --------------------------------------------------
# MONTHLY TREND
# --------------------------------------------------

st.subheader("Monthly Statistical Trend")

if filtered_data.empty:
    st.warning("No observations match the selected filters.")
else:
    fig = px.line(
        filtered_data,
        x="reference_month",
        y="value",
        markers=True,
        custom_data=["status_symbol", "symbol"],
        labels={
            "reference_month": "Reference Month",
            "value": f"Value ({selected_unit})",
        },
        title=f"{selected_commodity} — {selected_measure}",
    )

    fig.update_traces(
        connectgaps=False,
        hovertemplate=(
            "Month: %{x}<br>"
            "Value: %{y}<br>"
            "Status: %{customdata[0]}<br>"
            "Symbol: %{customdata[1]}"
            "<extra></extra>"
        ),
    )

    fig.update_layout(height=500)

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# --------------------------------------------------
# OBSERVATION DETAILS
# --------------------------------------------------

st.divider()

st.subheader("Monthly Observation Details")

display_columns = [
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
]

st.dataframe(
    filtered_data[display_columns],
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Source: Statistics Canada, Table 16-10-0019-01. "
    "Missing or suppressed values are preserved and are not treated as zero."
)
