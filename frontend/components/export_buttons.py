import io
import json
import streamlit as st
import pandas as pd


def render_export_buttons(df: pd.DataFrame, city_name: str = "properties"):
    """
    Renders download buttons allowing one-click export of data to CSV and JSON formats (in English).
    """
    if df.empty:
        return

    st.markdown('<div class="section-title">Export Data</div>', unsafe_allow_html=True)
    
    clean_city = city_name.lower().replace(" ", "_").replace(",", "")

    # CSV Buffer with utf-8-sig
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    
    # JSON Buffer
    json_str = df.to_json(orient="records", force_ascii=False, indent=2)
    json_bytes = json_str.encode("utf-8")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        st.download_button(
            label="Download CSV (Excel)",
            data=csv_bytes,
            file_name=f"properties_{clean_city}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        st.download_button(
            label="Download JSON",
            data=json_bytes,
            file_name=f"properties_{clean_city}.json",
            mime="application/json",
            use_container_width=True
        )

    with col3:
        st.caption(f"Consolidated file with **{len(df)}** records and **{len(df.columns)}** structured fields.")
