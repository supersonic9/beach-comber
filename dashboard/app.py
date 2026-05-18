import os
from datetime import date

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

AREAS = ["Póvoa de Varzim", "Vila do Conde", "Matosinhos", "Vila Nova de Gaia"]
PROPERTY_TYPES = [
    "apartamentos", "moradias", "terrenos", "lojas", "escritorios",
    "predios", "armazens", "quintas-e-herdades", "garagens", "luxo",
]

PROPERTY_TYPE_LABELS: dict[str, str] = {
    "apartamentos": "Apartamentos / Apartments",
    "moradias": "Moradias / Houses",
    "terrenos": "Terrenos / Land",
    "lojas": "Lojas / Shops",
    "escritorios": "Escritórios / Offices",
    "predios": "Prédios / Buildings",
    "armazens": "Armazéns / Warehouses",
    "quintas-e-herdades": "Quintas e Herdades / Farms & Estates",
    "garagens": "Garagens / Garages",
    "luxo": "Imóveis de Luxo / Luxury Properties",
}


def _connect() -> psycopg2.extensions.connection:
    url = os.environ.get("DATABASE_URL")
    if not url:
        st.error("DATABASE_URL not set")
        st.stop()
    return psycopg2.connect(url)


@st.cache_data(ttl=300)
def load_listings() -> pd.DataFrame:
    conn = _connect()
    try:
        query = """
            SELECT
                l.id,
                l.property_type,
                l.search_area,
                l.location,
                l.bedrooms,
                l.price,
                l.price_per_sqm,
                l.size_sqm,
                l.condition,
                l.url,
                l.first_seen,
                l.last_seen,
                l.is_active,
                COALESCE(first_snap.price, l.price) AS first_price
            FROM listings l
            LEFT JOIN price_snapshots first_snap ON (
                first_snap.listing_id = l.id
                AND first_snap.scraped_at = l.first_seen
            )
        """
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    df["price_change_pct"] = (
        (df["price"] - df["first_price"]) / df["first_price"].replace(0, pd.NA) * 100
    ).round(1)
    df["url"] = df["url"].apply(
        lambda u: "https://casa.sapo.pt" + u if pd.notna(u) and str(u).startswith("/") else u
    )
    return df


@st.cache_data(ttl=300)
def load_snapshots() -> pd.DataFrame:
    conn = _connect()
    try:
        query = """
            SELECT ps.listing_id, ps.scraped_at, ps.price,
                   l.search_area, l.property_type
            FROM price_snapshots ps
            JOIN listings l ON l.id = ps.listing_id
            ORDER BY ps.scraped_at
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    if filters["areas"]:
        df = df[df["search_area"].isin(filters["areas"])]
    if filters["types"]:
        df = df[df["property_type"].isin(filters["types"])]
    if filters["bedrooms"]:
        df = df[df["bedrooms"].isin(filters["bedrooms"])]
    price_upper = filters["price_max"]
    if price_upper >= 3_000_000:
        df = df[df["price"].isna() | (df["price"] >= filters["price_min"])]
    else:
        df = df[
            df["price"].isna()
            | ((df["price"] >= filters["price_min"]) & (df["price"] <= price_upper))
        ]
    if filters["size_min"] > 0 or filters["size_max"] < 2000:
        df = df[
            df["size_sqm"].isna()
            | ((df["size_sqm"] >= filters["size_min"]) & (df["size_sqm"] <= filters["size_max"]))
        ]
    if filters["active_only"]:
        df = df[df["is_active"] == True]  # noqa: E712
    return df


def sidebar_filters(df: pd.DataFrame) -> dict:
    st.sidebar.header("Filters")

    areas = st.sidebar.multiselect("Area", AREAS, default=[])
    type_label_options = [PROPERTY_TYPE_LABELS[t] for t in PROPERTY_TYPES]
    selected_labels = st.sidebar.multiselect("Property type", type_label_options, default=[])
    label_to_slug = {v: k for k, v in PROPERTY_TYPE_LABELS.items()}
    types = [label_to_slug[lbl] for lbl in selected_labels]

    bedroom_opts = ["T0", "T1", "T2", "T3", "T4", "T5+"]
    bedrooms = st.sidebar.multiselect("Bedrooms", bedroom_opts, default=[])

    _PRICE_OPTS = list(range(0, 3_010_000, 10_000))
    price_min, price_max = st.sidebar.select_slider(
        "Price (€)",
        options=_PRICE_OPTS,
        value=(0, 3_000_000),
        format_func=lambda x: f"€{x:,}{'+'  if x == 3_000_000 else ''}",
    )

    size_min, size_max = st.sidebar.slider(
        "Size (m²)", min_value=0, max_value=2000, value=(0, 2000), step=10
    )

    active_only = st.sidebar.toggle("Active listings only", value=True)

    return {
        "areas": areas,
        "types": types,
        "bedrooms": bedrooms,
        "price_min": price_min,
        "price_max": price_max,
        "size_min": size_min,
        "size_max": size_max,
        "active_only": active_only,
    }


def tab_listings(df: pd.DataFrame) -> None:
    display = df[[
        "search_area", "property_type", "bedrooms", "price", "price_change_pct",
        "size_sqm", "price_per_sqm", "location", "condition", "first_seen", "last_seen", "url",
    ]].copy()
    display["price"] = display["price"].apply(lambda x: f"€{int(x):,}" if pd.notna(x) else "—")
    display["price_per_sqm"] = display["price_per_sqm"].apply(lambda x: f"€{float(x):,.0f}" if pd.notna(x) else "—")
    display["price_change_pct"] = display["price_change_pct"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    display.columns = [
        "Area", "Type", "Beds", "Price (€)", "Change %",
        "Size m²", "€/m²", "Location", "Condition", "First seen", "Last seen", "Link",
    ]
    st.dataframe(display, use_container_width=True)
    st.caption(f"{len(df):,} listings")


def tab_price_trends(df: pd.DataFrame, snapshots: pd.DataFrame) -> None:
    if snapshots.empty:
        st.info("No snapshot data yet.")
        return

    listing_ids = set(df["id"])
    snaps = snapshots[snapshots["listing_id"].isin(listing_ids)].copy()
    if snaps.empty:
        st.info("No snapshot data for current filter.")
        return

    snaps["scraped_at"] = pd.to_datetime(snaps["scraped_at"])
    size_map = df.set_index("id")["size_sqm"].to_dict()
    snaps["size_sqm"] = snaps["listing_id"].map(size_map)
    snaps["snap_price_per_sqm"] = snaps.apply(
        lambda r: r["price"] / float(r["size_sqm"])
        if pd.notna(r["size_sqm"]) and float(r["size_sqm"]) > 0
        else None,
        axis=1,
    )

    trend = (
        snaps.groupby(["scraped_at", "search_area"])["snap_price_per_sqm"]
        .median()
        .reset_index()
    )
    trend.columns = ["Date", "Area", "Median €/m²"]

    fig = px.line(
        trend, x="Date", y="Median €/m²", color="Area", markers=True,
        title="Median price/m² over time by area",
    )
    st.plotly_chart(fig, use_container_width=True)


def tab_price_movers(df: pd.DataFrame) -> None:
    movers = df[df["price_change_pct"].notna()].copy()
    if movers.empty:
        st.info("No price change data yet — needs at least 2 scrape runs.")
        return

    cols = ["search_area", "property_type", "bedrooms", "price", "price_change_pct", "url"]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top 20 drops")
        drops = movers.nsmallest(20, "price_change_pct")[cols].copy()
        drops["price_change_pct"] = drops["price_change_pct"].apply(lambda x: f"{x:+.1f}%")
        drops["price"] = drops["price"].apply(lambda x: f"€{int(x):,}" if pd.notna(x) else "—")
        st.dataframe(drops.rename(columns={
            "search_area": "Area", "property_type": "Type", "bedrooms": "Beds",
            "price": "Price", "price_change_pct": "Change", "url": "Link",
        }), use_container_width=True)

    with col2:
        st.subheader("Top 20 rises")
        rises = movers.nlargest(20, "price_change_pct")[cols].copy()
        rises["price_change_pct"] = rises["price_change_pct"].apply(lambda x: f"{x:+.1f}%")
        rises["price"] = rises["price"].apply(lambda x: f"€{int(x):,}" if pd.notna(x) else "—")
        st.dataframe(rises.rename(columns={
            "search_area": "Area", "property_type": "Type", "bedrooms": "Beds",
            "price": "Price", "price_change_pct": "Change", "url": "Link",
        }), use_container_width=True)


def tab_new_listings(df: pd.DataFrame, snapshots: pd.DataFrame) -> None:
    if snapshots.empty:
        st.info("No snapshot data yet.")
        return

    latest_scrape = snapshots["scraped_at"].max()
    new = df[df["first_seen"] == latest_scrape]
    st.caption(f"Most recent scrape: {latest_scrape} — {len(new):,} new listings")

    if new.empty:
        st.info("No new listings from latest scrape.")
        return

    display = new[[
        "search_area", "property_type", "bedrooms", "price",
        "size_sqm", "price_per_sqm", "location", "url",
    ]].copy()
    display["price"] = display["price"].apply(lambda x: f"€{int(x):,}" if pd.notna(x) else "—")
    display["price_per_sqm"] = display["price_per_sqm"].apply(lambda x: f"€{float(x):,.0f}" if pd.notna(x) else "—")
    st.dataframe(display.rename(columns={
        "search_area": "Area", "property_type": "Type", "bedrooms": "Beds",
        "price": "Price", "size_sqm": "Size m²", "price_per_sqm": "€/m²",
        "location": "Location", "url": "Link",
    }), use_container_width=True)


def tab_market_volume(df: pd.DataFrame, snapshots: pd.DataFrame) -> None:
    if snapshots.empty:
        st.info("No snapshot data yet.")
        return

    listing_ids = set(df["id"])
    snaps = snapshots[snapshots["listing_id"].isin(listing_ids)].copy()
    if snaps.empty:
        st.info("No snapshot data for current filter.")
        return

    snaps["week"] = pd.to_datetime(snaps["scraped_at"]).dt.to_period("W").apply(lambda p: p.start_time)
    vol = (
        snaps.groupby(["week", "search_area"])["listing_id"]
        .nunique()
        .reset_index()
    )
    vol.columns = ["Week", "Area", "Listings"]

    fig = px.bar(vol, x="Week", y="Listings", color="Area", barmode="stack",
                 title="Listing count per area per week")
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Beach Comber", page_icon="🏠", layout="wide")
    st.title("Beach Comber — Portugal Property Tracker")

    with st.spinner("Loading data..."):
        df = load_listings()
        snapshots = load_snapshots()

    filters = sidebar_filters(df)
    filtered = apply_filters(df, filters)

    tabs = st.tabs(["Listings", "Price trends", "Price movers", "New listings", "Market volume"])

    with tabs[0]:
        tab_listings(filtered)
    with tabs[1]:
        tab_price_trends(filtered, snapshots)
    with tabs[2]:
        tab_price_movers(filtered)
    with tabs[3]:
        tab_new_listings(filtered, snapshots)
    with tabs[4]:
        tab_market_volume(filtered, snapshots)


if __name__ == "__main__":
    main()
