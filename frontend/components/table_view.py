import re
import streamlit as st
import pandas as pd


def _parse_price_to_number(price_str: str) -> float:
    """Extracts clean float value from currency string (e.g. 'R$ 850.000' -> 850000.0)."""
    if not isinstance(price_str, str) or not price_str.strip():
        return 0.0
    clean_str = price_str.strip().lower()
    if clean_str in ["none", "null", "n/a", "consulte", "sob consulta", "0"]:
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", price_str)
    if not cleaned:
        return 0.0
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) == 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            cleaned = "".join(parts)
        else:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def render_table_view(df: pd.DataFrame):
    """
    Renders an interactive, searchable and filterable table of property listings.
    """
    if df.empty:
        st.info("No property listings available to display.")
        return

    st.markdown('<div class="section-title">Property Listings Table</div>', unsafe_allow_html=True)

    # Compute numeric price for filtering
    working_df = df.copy()
    working_df["_numeric_price"] = working_df["price"].apply(_parse_price_to_number)

    # Filtering row 1: Text search, Neighborhood, Bedrooms
    col1, col2, col3 = st.columns([2, 1.5, 1])
    
    with col1:
        search_query = st.text_input("Filter by keyword (title, neighborhood, street)", value="")
    
    with col2:
        neighborhoods = ["All"]
        if "neighborhood" in working_df.columns:
            valid_neighs = sorted([str(n) for n in working_df["neighborhood"].dropna().unique() if str(n).strip()])
            neighborhoods.extend(valid_neighs)
        selected_neigh = st.selectbox("Neighborhood / Area", options=neighborhoods, index=0)

    with col3:
        bedroom_opts = ["All", "1+", "2+", "3+", "4+"]
        selected_beds = st.selectbox("Bedrooms", options=bedroom_opts, index=0)

    # Filtering row 2: Price filtering & None price exclusion
    col_p1, col_p2, col_p3 = st.columns([1.5, 1.5, 1.5])
    
    with col_p1:
        min_price_val = st.number_input(
            "Min Price (R$)",
            min_value=0.0,
            value=0.0,
            step=50000.0,
            format="%.0f",
            help="Filter properties with price greater than or equal to this amount."
        )

    with col_p2:
        max_price_val = st.number_input(
            "Max Price (R$)",
            min_value=0.0,
            value=0.0,
            step=50000.0,
            format="%.0f",
            help="Filter properties with price up to this amount (0 = no upper limit)."
        )

    with col_p3:
        st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
        exclude_none_price = st.checkbox(
            "Exclude No Price (None / R$ 0)",
            value=True,
            help="Hides listings with unstated, sob consulta, or zero prices."
        )

    # Apply filters
    filtered_df = working_df.copy()

    # 1. Price filters
    if exclude_none_price:
        filtered_df = filtered_df[filtered_df["_numeric_price"] > 0]

    if min_price_val > 0:
        filtered_df = filtered_df[filtered_df["_numeric_price"] >= min_price_val]

    if max_price_val > 0:
        filtered_df = filtered_df[filtered_df["_numeric_price"] <= max_price_val]

    # 2. Text keyword filter
    if search_query.strip():
        q = search_query.strip().lower()
        match_title = filtered_df["title"].astype(str).str.lower().str.contains(q, na=False)
        match_neigh = filtered_df.get("neighborhood", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        match_desc = filtered_df.get("description", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        filtered_df = filtered_df[match_title | match_neigh | match_desc]

    # 3. Neighborhood filter
    if selected_neigh != "All" and "neighborhood" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["neighborhood"] == selected_neigh]

    # 4. Bedroom filter
    if selected_beds != "All" and "bedrooms" in filtered_df.columns:
        min_beds = int(selected_beds.replace("+", ""))
        filtered_df = filtered_df[pd.to_numeric(filtered_df["bedrooms"], errors="coerce") >= min_beds]

    # 5. Always sort from lowest to highest price (ascending order)
    filtered_df = filtered_df.sort_values(by="_numeric_price", ascending=True)

    st.caption(f"Displaying **{len(filtered_df)}** of **{len(df)}** listings (ordered from lowest to highest price).")

    # Configure columns for optimal interactive display
    column_config = {
        "title": st.column_config.TextColumn("Title / Headline", width="large"),
        "price": st.column_config.TextColumn("Price", width="medium"),
        "property_type": st.column_config.TextColumn("Type", width="small"),
        "neighborhood": st.column_config.TextColumn("Neighborhood", width="medium"),
        "bedrooms": st.column_config.NumberColumn("Bedrooms", width="small"),
        "suites": st.column_config.NumberColumn("Suites", width="small"),
        "area_m2": st.column_config.NumberColumn("Area (m²)", format="%.0f m²", width="small"),
        "source_url": st.column_config.LinkColumn("Listing Link", width="medium")
    }

    # Desired column order
    ordered_cols = [
        "title", "price", "property_type", "neighborhood",
        "bedrooms", "suites", "area_m2", "source_url"
    ]
    present_cols = [c for c in ordered_cols if c in filtered_df.columns]
    extra_cols = [c for c in filtered_df.columns if c not in present_cols and c not in ["parking_spots", "bathrooms", "description", "address", "city", "condo_fee", "iptu", "amenities", "financing_accepted", "highlights", "transaction_type"]]

    st.dataframe(
        filtered_df[present_cols + extra_cols],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=400
    )
