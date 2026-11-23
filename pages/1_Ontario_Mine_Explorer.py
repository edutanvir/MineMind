import html

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from src.analytics.mine_queries import with_primary_commodity
from src.database.duckdb_manager import get_duckdb_connection
from src.ui.theme import inject_css


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

# --------------------------------------------------
# DYNAMIC PAGE CONFIGURATION
# --------------------------------------------------

current_province = st.session_state.get(
    "mine_province",
    "All Provinces",
)

if current_province == "All Provinces":
    explorer_title = "Canadian Mine Explorer"
else:
    explorer_title = f"{current_province} Mine Explorer"

st.set_page_config(
    page_title=f"MineMind | {explorer_title}",
    page_icon="⛏️",
    layout="wide",
)

inject_css()


# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------

@st.cache_data(ttl=300)
def load_table(table_name):
    allowed_tables = {
        "dim_mine_feature",
        "fact_mineral_production_monthly",
    }

    if table_name not in allowed_tables:
        raise ValueError("Unsupported table.")

    con = get_duckdb_connection(read_only=True)

    try:
        return con.execute(
            f"SELECT * FROM {table_name}"
        ).df()
    finally:
        con.close()


try:
    mines = with_primary_commodity(load_table("dim_mine_feature"))
    production = load_table("fact_mineral_production_monthly")

except Exception as error:
    st.error(f"Unable to load MineMind datasets: {error}")
    st.stop()


# --------------------------------------------------
# CANADIAN MINE FEATURES
# --------------------------------------------------

all_mines = mines.copy()

all_mines["latitude"] = pd.to_numeric(
    all_mines["latitude"], errors="coerce"
)

all_mines["longitude"] = pd.to_numeric(
    all_mines["longitude"], errors="coerce"
)


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

st.title(explorer_title)

st.markdown(
    f"Explore mapped {current_province.lower() if current_province != 'All Provinces' else 'Canadian'} "
    "mine and facility features, and examine monthly mineral "
    "production and value-of-shipments statistics."
)

st.info(
    "The mine map uses Natural Resources Canada features. "
    "Production and shipment statistics come from Statistics "
    f"Canada and represent {current_province.lower() if current_province != 'All Provinces' else 'Canadian'} as a whole—not individual mines."
)

st.divider()

# --------------------------------------------------
# FILTER RESET CALLBACKS
# --------------------------------------------------

def reset_province_filters():
    """Clear dependent selections when province changes."""
    for key in [
        "mine_city",
        "mine_commodities",
        "mine_feature_types",
    ]:
        st.session_state.pop(key, None)


def reset_city_filters():
    """Clear dependent selections when city changes."""
    for key in [
        "mine_commodities",
        "mine_feature_types",
    ]:
        st.session_state.pop(key, None)

# --------------------------------------------------
# MINE FILTERS
# --------------------------------------------------

st.sidebar.header("Mine Explorer Filters")

province_options = sorted(
    all_mines["province"].dropna().unique()
)

selected_province = st.sidebar.selectbox(
    "Province / Territory",
    ["All Provinces"] + province_options,
    key="mine_province",
    on_change=reset_province_filters,
)

if selected_province == "All Provinces":
    province_mines = all_mines.copy()
else:
    province_mines = all_mines[
        all_mines["province"].eq(selected_province)
    ].copy()

# City filter depends on selected province
city_options = sorted(
    province_mines["city"].dropna().unique()
)

selected_city = st.sidebar.selectbox(
    "City",
    ["All Cities"] + city_options,
    key="mine_city",
    on_change=reset_city_filters,
)

if selected_city != "All Cities":
    province_mines = province_mines[
        province_mines["city"].eq(selected_city)
    ].copy()

# --------------------------------------------------
# PROVINCE-SPECIFIC COMMODITY FILTER
# --------------------------------------------------

commodity_options = sorted(
    province_mines["commodity_normalized"]
    .dropna()
    .unique()
)

commodity_filter_key = (
    f"mine_commodities_{selected_province}_{selected_city}"
)

selected_commodities = st.sidebar.multiselect(
    "Commodity",
    options=commodity_options,
    default=commodity_options,
    key=commodity_filter_key,
)

# --------------------------------------------------
# PROVINCE-SPECIFIC FEATURE TYPE FILTER
# --------------------------------------------------

feature_options = sorted(
    province_mines["feature_type"]
    .dropna()
    .unique()
)

feature_filter_key = (
    f"mine_features_{selected_province}_{selected_city}"
)

selected_features = st.sidebar.multiselect(
    "Feature Type",
    options=feature_options,
    default=feature_options,
    key=feature_filter_key,
)

filtered_mines = province_mines[
    province_mines["commodity_normalized"].isin(
        selected_commodities
    )
    & province_mines["feature_type"].isin(
        selected_features
    )
].copy()

filtered_mapped = filtered_mines.dropna(
    subset=["latitude", "longitude"]
).copy()

# --------------------------------------------------
# MINE KPIs
# --------------------------------------------------

st.subheader("Mining Companies and Mine Features")

company_count = (
    filtered_mines["operator_name"]
    .dropna()
    .astype(str)
    .str.strip()
    .loc[lambda values: values.ne("")]
    .nunique()
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Mapped Mine Features",
    f"{len(filtered_mapped):,}",
)

col2.metric(
    "Mining Companies / Operators",
    f"{company_count:,}",
)

col3.metric(
    "Commodity Categories",
    f"{filtered_mines['commodity_normalized'].nunique():,}",
)

col4.metric(
    "Named Features",
    f"{filtered_mines['feature_name'].nunique():,}",
)

st.caption(
    "Company counts represent distinct non-empty operator names "
    "in the Natural Resources Canada dataset. They are not "
    "necessarily counts of unique legal corporate entities."
)

st.divider()


# --------------------------------------------------
# INTERACTIVE MINE MAP
# --------------------------------------------------

st.subheader("Mine Locations")

if filtered_mapped.empty:
    st.warning("No mapped features match the selected filters.")

else:
    center_lat = filtered_mapped["latitude"].median()
    center_lon = filtered_mapped["longitude"].median()

    mine_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    commodity_colors = {
        "Gold": "orange",
        "Copper": "red",
        "Nickel": "blue",
        "Limestone": "green",
        "Salt": "purple",
    }

    for _, mine in filtered_mapped.iterrows():
        name = html.escape(
            str(mine["feature_name"])
            if pd.notna(mine["feature_name"])
            else "Unnamed feature"
        )

        operator = html.escape(
            str(mine["operator_name"])
            if pd.notna(mine["operator_name"])
            else "Not available"
        )

        commodity = html.escape(
            str(mine["commodity_raw"])
            if pd.notna(mine["commodity_raw"])
            else "Not available"
        )

        feature_type = html.escape(
            str(mine["feature_type"])
            if pd.notna(mine["feature_type"])
            else "Not available"
        )

        facilities = html.escape(
            str(mine["facilities_type"])
            if pd.notna(mine["facilities_type"])
            else "Not available"
        )

        color = commodity_colors.get(
            mine["commodity_normalized"],
            "gray",
        )

        province = html.escape(str(mine["province"]))

        popup_html = f"""
        <div style="width:250px">
            <h4>{name}</h4>
            <b>Operator:</b> {operator}<br>
            <b>Commodity:</b> {commodity}<br>
            <b>Feature type:</b> {feature_type}<br>
            <b>Facilities:</b> {facilities}<br>
            <b>Province:</b> {province}
        </div>
        """

        folium.CircleMarker(
            location=[
                mine["latitude"],
                mine["longitude"],
            ],
            radius=7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            weight=1,
            tooltip=name,
            popup=folium.Popup(
                popup_html,
                max_width=300,
            ),
        ).add_to(mine_map)

    st_folium(
        mine_map,
        width=1200,
        height=650,
        returned_objects=[],
    )

    st.caption(
        "Select a map marker to view its feature name, operator, "
        "commodity, feature type and facility information. "
        "Marker colours distinguish selected commodity categories."
    )

    


# --------------------------------------------------
# MINE FEATURE DETAILS
# --------------------------------------------------

st.divider()

st.subheader(
    f"{current_province} Mine Feature Details"
    if current_province != "All Provinces"
    else "Canadian Mine Feature Details"
)

detail_columns = [
    "feature_name",
    "operator_name",
    "city",
    "commodity_normalized",
    "commodity_raw",
    "feature_type",
    "facilities_type",
    "latitude",
    "longitude",
]

st.dataframe(
    filtered_mapped[detail_columns].sort_values(
        ["commodity_normalized", "feature_name"],
        na_position="last",
    ),
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# ONTARIO PROVINCIAL PRODUCTION DATA
# --------------------------------------------------

st.divider()

st.title(
    f"{current_province} Mineral Production and Shipments"
    if current_province != "All Provinces"
    else "Canadian Mineral Production and Shipments"
)

st.markdown(
    f"Explore {current_province.lower() if current_province != 'All Provinces' else 'Canadian'}'s reported monthly mineral statistics. "
    f"Choose one exact statistical series to avoid mixing "
    f"different mineral products or measurement units."
)

# --------------------------------------------------
# SELECTED PROVINCE PRODUCTION DATA
# --------------------------------------------------

if selected_province == "All Provinces":
    st.info(
        "Select a province to explore its production statistics. "
        "National and regional totals are not added together."
    )
    st.stop()

province_production = production[
    production["geography"].eq(selected_province)
].copy()

if province_production.empty:
    st.warning(f"No {selected_province} production observations were found.")
    st.stop()



# --------------------------------------------------
# PRODUCTION FILTERS — DATA-AWARE CASCADING FILTERS
# --------------------------------------------------

st.sidebar.divider()
st.sidebar.header(f"{selected_province} Production Filters")

# Only measures with actual numerical observations
usable_production = province_production[
    province_production["value"].notna() & province_production["value"].ne(0)
].copy()

measure_summary = (
    usable_production
    .groupby("measure")
    .agg(
        available_observations=("value", "count")
    )
    .reset_index()
)

measure_options = sorted(
    measure_summary["measure"].unique()
)

if not measure_options:
    st.warning(
        f"No numerical production observations are available "
        f"for {selected_province}."
    )
    st.stop()

measure_counts = dict(
    zip(
        measure_summary["measure"],
        measure_summary["available_observations"],
    )
)

default_measure = (
    "Quantity produced"
    if "Quantity produced" in measure_options
    else measure_options[0]
)

selected_measure = st.sidebar.selectbox(
    "Statistical Measure",
    options=measure_options,
    index=measure_options.index(default_measure),
    format_func=lambda x: (
        f"{x} ({measure_counts[x]:,} observations)"
    ),
)

# Preserve all records for the selected measure,
# including missing values for data-quality analysis.
measure_data = province_production[
    province_production["measure"].eq(selected_measure)
].copy()


# --------------------------------------------------
# COMMODITY FILTER — ONLY COMMODITIES WITH DATA
# --------------------------------------------------

commodity_summary = (
    measure_data
    .dropna(subset=["value"])
    .loc[lambda df: df["value"].ne(0)]
    .groupby("commodity")
    .agg(
        available_observations=("value", "count"),
        first_month=("reference_month", "min"),
        latest_month=("reference_month", "max"),
    )
    .reset_index()
)

commodity_summary = commodity_summary.sort_values(
    "commodity"
)

commodity_options = commodity_summary["commodity"].tolist()

if not commodity_options:
    st.warning(
        f"No commodities have numerical observations for "
        f"{selected_province} under {selected_measure}."
    )
    st.stop()

commodity_counts = dict(
    zip(
        commodity_summary["commodity"],
        commodity_summary["available_observations"],
    )
)

selected_commodity = st.sidebar.selectbox(
    "Production Commodity",
    options=commodity_options,
    format_func=lambda x: (
        f"{x} ({commodity_counts[x]:,} observations)"
    ),
)

commodity_data = measure_data[
    measure_data["commodity"].eq(selected_commodity)
].copy()


# --------------------------------------------------
# MEASUREMENT UNIT — ONLY UNITS WITH DATA
# --------------------------------------------------

unit_summary = (
    commodity_data
    .dropna(subset=["value"])
    .loc[lambda df: df["value"].ne(0)]
    .groupby("unit")
    .agg(
        available_observations=("value", "count")
    )
    .reset_index()
)

unit_options = sorted(unit_summary["unit"].unique())

if not unit_options:
    st.warning("No measurement units have available numerical data.")
    st.stop()

unit_counts = dict(
    zip(
        unit_summary["unit"],
        unit_summary["available_observations"],
    )
)

selected_unit = st.sidebar.selectbox(
    "Measurement Unit",
    options=unit_options,
    format_func=lambda x: (
        f"{x} ({unit_counts[x]:,} observations)"
    ),
)

unit_data = commodity_data[
    commodity_data["unit"].eq(selected_unit)
].copy()


# --------------------------------------------------
# EXACT SERIES SELECTION
# --------------------------------------------------

series_columns = [
    "commodity_raw",
    "vector",
    "coordinate",
]

available_series = (
    unit_data[
        unit_data["value"].notna()
        & unit_data["value"].ne(0)
    ][series_columns]
    .drop_duplicates()
    .sort_values(
        series_columns,
        na_position="last",
    )
)


def format_series(row):
    raw, vector, coordinate = row

    return (
        f"{raw} | "
        f"Vector: {vector if pd.notna(vector) else 'N/A'} | "
        f"Coordinate: {coordinate if pd.notna(coordinate) else 'N/A'}"
    )


series_options = [
    (row.commodity_raw, row.vector, row.coordinate)
    for row in available_series.itertuples(index=False)
]


if not series_options:
    st.warning("No exact statistical series are available.")
    st.stop()

selected_series = st.sidebar.selectbox(
    "Exact Statistical Series",
    series_options,
    format_func=format_series,
)

selected_raw, selected_vector, selected_coordinate = selected_series


def matches_value(series, selected):
    if pd.isna(selected):
        return series.isna()

    return series.eq(selected)


series_data = unit_data[
    matches_value(
        unit_data["commodity_raw"],
        selected_raw,
    )
    & matches_value(
        unit_data["vector"],
        selected_vector,
    )
    & matches_value(
        unit_data["coordinate"],
        selected_coordinate,
    )
].copy()


# --------------------------------------------------
# DATE FILTER
# --------------------------------------------------

month_options = sorted(
    series_data["reference_month"].dropna().unique()
)

if not month_options:
    st.warning("No monthly observations are available.")
    st.stop()

selected_months = st.sidebar.select_slider(
    "Production Date Range",
    options=month_options,
    value=(month_options[0], month_options[-1]),
)

filtered_production = series_data[
    series_data["reference_month"].between(
        selected_months[0],
        selected_months[1],
    )
].copy()

filtered_production = filtered_production.sort_values(
    "reference_month"
)


# --------------------------------------------------
# PRODUCTION SERIES INFORMATION
# --------------------------------------------------

st.subheader(f"Selected {current_province} Statistical Series")

st.caption(
    f"Commodity: {selected_commodity} | "
    f"Measure: {selected_measure} | "
    f"Unit: {selected_unit}"
)

if (
    selected_unit == "Dollars"
    and selected_measure != "Value of shipments"
):
    st.warning(
        "This is a monetary-valued series, not a physical "
        "production quantity."
    )

if selected_measure == "Value of shipments":
    st.info(
        "Value of shipments is the reported value of mineral "
        "shipments in Ontario. It is not company profit, net "
        "income, or the earnings of an individual mine."
    )


# --------------------------------------------------
# DATA QUALITY CHECK
# --------------------------------------------------

duplicate_months = filtered_production[
    filtered_production.duplicated(
        subset=["reference_month"],
        keep=False,
    )
]

if not duplicate_months.empty:
    st.error(
        "Multiple observations exist for a month in this exact "
        "series. The trend is stopped to avoid accidental aggregation."
    )
    st.dataframe(duplicate_months, use_container_width=True)
    st.stop()


# --------------------------------------------------
# PRODUCTION KPIs
# --------------------------------------------------

available = filtered_production.dropna(
    subset=["value"]
)

latest_record = (
    available.sort_values("reference_month").iloc[-1]
    if not available.empty
    else None
)

total_observations = len(filtered_production)
missing_values = filtered_production["value"].isna().sum()

col1, col2, col3 = st.columns(3)

col1.metric(
    "Monthly Observations",
    f"{total_observations:,}",
)

col2.metric(
    "Missing / Suppressed",
    f"{missing_values:,}",
)

if latest_record is not None:
    latest_value = latest_record["value"]
    latest_month = latest_record["reference_month"]

    col3.metric(
        "Latest Available Value",
        f"{latest_value:,.2f} {selected_unit}",
        help=f"Latest available observation: {latest_month}",
    )
else:
    col3.metric(
        "Latest Available Value",
        "Unavailable",
    )


# --------------------------------------------------
# MONTHLY TREND
# --------------------------------------------------

st.divider()

st.subheader(f"{current_province} Monthly Trend")

if filtered_production.empty:
    st.warning("No observations match the selected filters.")

else:
    fig = px.line(
        filtered_production,
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
# MONTHLY OBSERVATION DETAILS
# --------------------------------------------------

st.subheader(f"{current_province} Monthly Observation Details")

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
    filtered_production[display_columns],
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Sources: Natural Resources Canada, Map 900A; "
    "Statistics Canada, Table 16-10-0019-01. "
    "Production statistics are provincial and are not attributed "
    "to individual mine locations. Suppressed values remain missing."
)
