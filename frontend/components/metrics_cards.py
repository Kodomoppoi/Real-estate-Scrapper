import re
import pandas as pd
import streamlit as st


def _parse_price_to_number(price_str: str) -> float:
    """Extracts clean float value from currency string."""
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


def render_metrics_cards(df: pd.DataFrame):
    """
    Renders stylish minimalist KPI cards summarizing the scraped property dataset (in English).
    """
    if df.empty:
        return

    total_listings = len(df)
    
    # Calculate price metrics
    price_series = df["price"].dropna().apply(_parse_price_to_number)
    valid_prices = price_series[price_series > 0]
    
    avg_price_str = "N/A"
    if not valid_prices.empty:
        avg_val = valid_prices.mean()
        if avg_val >= 1_000_000:
            avg_price_str = f"R$ {avg_val / 1_000_000:.2f}M"
        else:
            avg_price_str = f"R$ {avg_val:,.0f}".replace(",", ".")

    # Calculate area metrics
    area_series = pd.to_numeric(df.get("area_m2"), errors="coerce").dropna()
    valid_areas = area_series[area_series > 0]
    median_area_str = f"{valid_areas.median():.0f} m²" if not valid_areas.empty else "N/A"

    # Calculate top neighborhood
    top_neighborhood = "Various"
    if "neighborhood" in df.columns:
        valid_neigh = df["neighborhood"].dropna()
        valid_neigh = valid_neigh[valid_neigh != ""]
        if not valid_neigh.empty:
            top_neighborhood = valid_neigh.mode().iloc[0]

    st.markdown(
        f"""
        <div class="metrics-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Listings</div>
                <div class="kpi-value">{total_listings}</div>
                <div class="kpi-subtext">Extracted properties</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Average Price</div>
                <div class="kpi-value">{avg_price_str}</div>
                <div class="kpi-subtext">Market estimate</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Median Area</div>
                <div class="kpi-value">{median_area_str}</div>
                <div class="kpi-subtext">Usable space per unit</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Top Neighborhood</div>
                <div class="kpi-value" style="font-size: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{top_neighborhood}</div>
                <div class="kpi-subtext">Highest concentration</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
