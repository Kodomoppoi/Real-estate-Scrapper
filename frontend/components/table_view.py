import streamlit as st
import pandas as pd


def render_table_view(df: pd.DataFrame):
    """
    Renders an interactive, searchable and filterable table of property listings (in English).
    """
    if df.empty:
        st.info("No property listings available to display.")
        return

    st.markdown('<div class="section-title">Property Listings Table</div>', unsafe_allow_html=True)

    # Search and filtering row
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search_query = st.text_input("Filter by keyword (title, neighborhood, street)", value="")
    
    with col2:
        neighborhoods = ["All"]
        if "neighborhood" in df.columns:
            valid_neighs = sorted([str(n) for n in df["neighborhood"].dropna().unique() if str(n).strip()])
            neighborhoods.extend(valid_neighs)
        selected_neigh = st.selectbox("Neighborhood / Area", options=neighborhoods, index=0)

    with col3:
        bedroom_opts = ["All", "1+", "2+", "3+", "4+"]
        selected_beds = st.selectbox("Bedrooms", options=bedroom_opts, index=0)

    # Apply filters
    filtered_df = df.copy()

    if search_query.strip():
        q = search_query.strip().lower()
        match_title = filtered_df["title"].astype(str).str.lower().str.contains(q, na=False)
        match_neigh = filtered_df.get("neighborhood", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        match_desc = filtered_df.get("description", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        filtered_df = filtered_df[match_title | match_neigh | match_desc]

    if selected_neigh != "All" and "neighborhood" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["neighborhood"] == selected_neigh]

    if selected_beds != "All" and "bedrooms" in filtered_df.columns:
        min_beds = int(selected_beds.replace("+", ""))
        filtered_df = filtered_df[pd.to_numeric(filtered_df["bedrooms"], errors="coerce") >= min_beds]

    st.caption(f"Displaying **{len(filtered_df)}** of **{len(df)}** listings.")

    # Configure columns for optimal interactive display
    column_config = {
        "title": st.column_config.TextColumn("Title / Headline", width="large"),
        "price": st.column_config.TextColumn("Price", width="medium"),
        "property_type": st.column_config.TextColumn("Type", width="small"),
        "neighborhood": st.column_config.TextColumn("Neighborhood", width="medium"),
        "bedrooms": st.column_config.NumberColumn("Bedrooms", width="small"),
        "suites": st.column_config.NumberColumn("Suites", width="small"),
        "bathrooms": st.column_config.NumberColumn("Bathrooms", width="small"),
        "parking_spots": st.column_config.NumberColumn("Parking", width="small"),
        "area_m2": st.column_config.NumberColumn("Area (m²)", format="%.0f m²", width="small"),
        "source_url": st.column_config.LinkColumn("Listing Link", width="medium")
    }

    # Desired column order
    ordered_cols = [
        "title", "price", "property_type", "neighborhood",
        "bedrooms", "suites", "bathrooms", "parking_spots", "area_m2", "source_url"
    ]
    present_cols = [c for c in ordered_cols if c in filtered_df.columns]
    extra_cols = [c for c in filtered_df.columns if c not in present_cols and c not in ["description", "address", "city", "condo_fee", "iptu", "amenities", "financing_accepted", "highlights"]]

    st.dataframe(
        filtered_df[present_cols + extra_cols],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=400
    )
