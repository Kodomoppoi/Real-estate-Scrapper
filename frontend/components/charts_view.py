import re
import streamlit as st
import pandas as pd


def _clean_price(price_str: str) -> float:
    if not isinstance(price_str, str):
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", price_str)
    if not cleaned:
        return 0.0
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned and cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def render_charts_view(df: pd.DataFrame):
    """
    Renders visual charts analyzing price distributions, neighborhoods, and property areas (in English).
    """
    if df.empty or len(df) < 2:
        return

    st.markdown('<div class="section-title">Market Visual Analytics</div>', unsafe_allow_html=True)

    chart_df = df.copy()
    chart_df["numeric_price"] = chart_df["price"].dropna().apply(_clean_price)
    chart_df["numeric_area"] = pd.to_numeric(chart_df.get("area_m2"), errors="coerce")
    chart_df["numeric_beds"] = pd.to_numeric(chart_df.get("bedrooms"), errors="coerce")

    col1, col2 = st.columns(2)

    with col1:
        # Chart 1: Neighborhood Listing Count
        if "neighborhood" in chart_df.columns:
            valid_n = chart_df[chart_df["neighborhood"].astype(str).str.strip() != ""]
            if not valid_n.empty:
                top_bairros = valid_n["neighborhood"].value_counts().head(8)
                st.markdown("**Properties per Neighborhood (Top 8)**")
                st.bar_chart(top_bairros, color="#807454")

    with col2:
        # Chart 2: Bedroom distribution
        valid_beds = chart_df["numeric_beds"].dropna().astype(int)
        if not valid_beds.empty:
            bed_counts = valid_beds.value_counts().sort_index()
            bed_counts.index = [f"{b} bedroom(s)" for b in bed_counts.index]
            st.markdown("**Bedroom Distribution**")
            st.bar_chart(bed_counts, color="#A3B8FF")

    # Chart 3: Area vs Price scatter
    scatter_data = chart_df[(chart_df["numeric_price"] > 0) & (chart_df["numeric_area"] > 0)]
    if len(scatter_data) >= 3:
        st.markdown("**Area (m²) vs Price (R$) Relation**")
        st.scatter_chart(
            scatter_data,
            x="numeric_area",
            y="numeric_price",
            color="#807454",
            size=None
        )
