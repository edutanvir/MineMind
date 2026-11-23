import pandas as pd
import streamlit as st
import plotly.express as px

from src.analytics.mine_queries import with_primary_commodity
from src.database.duckdb_manager import get_duckdb_connection
from src.ui.theme import inject_css


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="MineMind | Mining Intelligence",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()


# --------------------------------------------------
# DATABASE QUERIES
# --------------------------------------------------

@st.cache_data(ttl=300)
def load_data(query):
    """Execute a read-only query against the Gold datasets."""
    con = get_duckdb_connection(read_only=True)

    try:
        return con.execute(query).df()
    finally:
        con.close()


@st.cache_data(ttl=300)
def load_mine_data():
    return load_data("""
        SELECT *
        FROM dim_mine_feature
    """)

@st.cache_data(ttl=300)
def load_production_data():
    return load_data("""
        SELECT *
        FROM fact_mineral_production_monthly
    """)

@st.cache_data(ttl=300)
def load_production_summary():
    return load_data("""
        SELECT
            measure,
            COUNT(*) AS observation_count,
            COUNT(value) AS available_values,
            COUNT(*) FILTER (
                WHERE status_symbol IS NOT NULL
                  AND TRIM(status_symbol) <> ''
            ) AS flagged_observations
        FROM fact_mineral_production_monthly
        GROUP BY measure
        ORDER BY measure
    """)


@st.cache_data(ttl=300)
def load_source_manifest():
    return load_data("""
        SELECT
            title,
            publisher,
            source_vintage,
            retrieved_at,
            licence
        FROM source_manifest
        ORDER BY title
    """)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

try:
    mines = with_primary_commodity(load_mine_data())
    production = load_production_data()
    sources = load_source_manifest()

except Exception as error:
    st.error(f"Unable to load Gold datasets: {error}")
    st.stop()


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.title("⛏️ MineMind")

st.sidebar.caption("Canadian Mining Data Intelligence")

st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    ["Overview"],
)

st.sidebar.divider()

st.sidebar.caption(
    "Data sources: Natural Resources Canada "
    "and Statistics Canada"
)


# --------------------------------------------------
# GLOBAL FILTERS
# --------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("Global Filters")

# Exclude aggregate geographies from the province slicer.
aggregate_geographies = {
    "Canada",
    "Atlantic region",
    "Prairies region",
}


# Province slicer — single selection

province_options = sorted(
    (
        set(mines["province"].dropna().unique())
        | set(production["geography"].dropna().unique())
    ) - aggregate_geographies
)

selected_province = st.sidebar.selectbox(
    "Select Province / Territory",
    options=["All Provinces"] + province_options,
    index=0,
    key="global_province",
)


commodity_options = sorted(
    set(mines["commodity_normalized"].dropna().unique())
    | set(production["commodity"].dropna().unique())
)

measure_options = sorted(
    production["measure"].dropna().unique()
)

month_options = sorted(
    production["reference_month"].dropna().unique()
)

# Commodity slicer
selected_commodities = st.sidebar.multiselect(
    "Commodity",
    options=commodity_options,
    default=commodity_options,
    key="global_commodities",
)

# Production measure slicer
selected_measures = st.sidebar.multiselect(
    "Production Measure",
    options=measure_options,
    default=measure_options,
    key="global_measures",
)

# Date range slicer
selected_months = st.sidebar.select_slider(
    "Production Date Range",
    options=month_options,
    value=(month_options[0], month_options[-1]),
    key="global_date_range",
)


# --------------------------------------------------
# APPLY GLOBAL FILTERS
# --------------------------------------------------

if selected_province == "All Provinces":
    province_mines = mines.copy()
    province_production = production.copy()
else:
    province_mines = mines[
        mines["province"] == selected_province
    ].copy()

    province_production = production[
        production["geography"] == selected_province
    ].copy()

# Apply commodity selection
filtered_mines = province_mines[
    province_mines["commodity_normalized"].isin(
        selected_commodities
    )
].copy()

filtered_production = province_production[
    province_production["commodity"].isin(
        selected_commodities
    )
    & province_production["measure"].isin(
        selected_measures
    )
    & province_production["reference_month"].between(
        selected_months[0],
        selected_months[1],
    )
].copy()

# Recalculate production coverage
production_summary = (
    filtered_production
    .groupby("measure", dropna=False)
    .agg(
        observation_count=("measure", "size"),
        available_values=("value", "count"),
        flagged_observations=(
            "status_symbol",
            lambda values: values.notna().sum(),
        ),
    )
    .reset_index()
)


# --------------------------------------------------
# OVERVIEW PAGE
# --------------------------------------------------

st.title("Canadian Mining Intelligence")
st.markdown(
    "Explore Canadian mine locations and mineral production "
    "statistics through integrated analytical datasets."
)

st.divider()


# --------------------------------------------------
# KPI CARDS — RESPOND TO GLOBAL FILTERS
# --------------------------------------------------

total_mines = len(filtered_mines)

total_provinces = filtered_mines["province"].nunique()

total_commodities = (
    filtered_mines["commodity_normalized"].nunique()
)

total_observations = len(filtered_production)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Mine Features",
    f"{total_mines:,}",
)

col2.metric(
    "Provinces / Territories",
    f"{total_provinces:,}",
)

col3.metric(
    "Commodity Categories",
    f"{total_commodities:,}",
)

col4.metric(
    "Production Observations",
    f"{total_observations:,}",
)


st.divider()



# --------------------------------------------------
# MINE DISTRIBUTION
# --------------------------------------------------

st.subheader("Mine Distribution")

left, right = st.columns(2)

with left:
    province_data = (
        filtered_mines
        .groupby("province", dropna=False)
        .size()
        .reset_index(name="mine_count")
        .sort_values("mine_count", ascending=False)
    )

    province_data["province"] = (
        province_data["province"].fillna("Unknown")
    )

    fig_province = px.bar(
        province_data,
        x="mine_count",
        y="province",
        orientation="h",
        title="Mine Features by Province / Territory",
        labels={
            "mine_count": "Number of mine features",
            "province": "Province / Territory",
        },
        text="mine_count",
    )

    fig_province.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=450,
    )

    st.plotly_chart(
        fig_province,
        use_container_width=True,
    )

with right:
    commodity_data = (
        filtered_mines
        .groupby("commodity_normalized", dropna=False)
        .size()
        .reset_index(name="mine_count")
        .sort_values("mine_count", ascending=False)
    )

    commodity_data["commodity_normalized"] = (
        commodity_data["commodity_normalized"].fillna("Unknown")
    )

    fig_commodity = px.pie(
        commodity_data,
        names="commodity_normalized",
        values="mine_count",
        title="Mine Features by Commodity",
        hole=0.45,
    )

    fig_commodity.update_layout(height=450)

    st.plotly_chart(
        fig_commodity,
        use_container_width=True,
    )



st.divider()


# --------------------------------------------------
# STATISTICS CANADA PRODUCTION DATA COVERAGE
# --------------------------------------------------

st.subheader("Mineral Production Data Coverage")

st.caption(
    "Observation counts by statistical measure. "
    "These counts represent records, not production quantities."
)

fig_production = px.bar(
    production_summary,
    x="measure",
    y="observation_count",
    color="measure",
    text="observation_count",
    labels={
        "measure": "Statistical Measure",
        "observation_count": "Number of observations",
    },
)

fig_production.update_layout(
    showlegend=False,
    height=400,
)

st.plotly_chart(
    fig_production,
    use_container_width=True,
)

st.dataframe(
    production_summary,
    use_container_width=True,
    hide_index=True,
)


st.divider()


# --------------------------------------------------
# DATA SOURCES
# --------------------------------------------------

st.subheader("Data Sources")

st.dataframe(
    sources,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Mine location data: Natural Resources Canada, Map 900A. "
    "Mineral production statistics: Statistics Canada, "
    "Table 16-10-0019-01."
)
