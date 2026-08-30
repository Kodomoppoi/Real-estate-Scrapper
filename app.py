import asyncio
import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.pipeline import run_pipeline_async
from frontend.utils import attach_log_handler, get_log_handler
from frontend.components import (
    render_sidebar,
    render_metrics_cards,
    render_table_view,
    render_charts_view,
    render_extra_info_view,
    render_export_buttons,
)

# Page configuration
st.set_page_config(
    page_title="Real Estate Discovery & AI Extractor",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Attach live logging handler
attach_log_handler()

# Load and inject minimalist CSS
def _inject_custom_css():
    css_path = Path(__file__).parent / "frontend" / "styles.css"
    if css_path.exists():
        css_content = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)


_inject_custom_css()

# Initialize session state variables
if "current_df" not in st.session_state:
    st.session_state["current_df"] = pd.DataFrame()
if "current_city" not in st.session_state:
    st.session_state["current_city"] = ""
if "curated_sites" not in st.session_state:
    st.session_state["curated_sites"] = []


def main():
    # 1. Render Sidebar
    sidebar_params = render_sidebar()

    # 2. Minimalist Header Banner
    st.markdown(
        """
        <div class="header-container">
            <div>
                <h1 class="header-title">Real Estate Discovery & AI Extractor</h1>
                <p class="header-subtitle">
                    Intelligent real estate portal crawler with AI curation and structured extraction.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 3. Handle Historical File Selection
    history_file = sidebar_params.get("selected_history_file")
    if history_file and history_file.exists():
        try:
            loaded_df = pd.read_csv(history_file, encoding="utf-8-sig")
            st.session_state["current_df"] = loaded_df
            st.session_state["current_city"] = history_file.stem.replace("properties_", "").split("_202")[0].replace("_", " ").title()
            st.session_state["curated_sites"] = []
            st.success(f"Historical file loaded: **{history_file.name}** ({len(loaded_df)} properties)")
        except Exception as exc:
            st.error(f"Error loading historical file: {exc}")

    # 4. Handle Live Search Execution
    if sidebar_params.get("start_search") or sidebar_params.get("start_clicked"):
        country = sidebar_params["country"]
        city = sidebar_params["city"]
        prop_type = sidebar_params["property_type"]
        trans_type = sidebar_params["transaction_type"]
        max_curated = sidebar_params["max_curated_sites"]
        max_pages = sidebar_params["max_pages_per_site"]

        if not city.strip():
            st.warning("Please enter a city or location in the sidebar.")
            return

        # Prepare Live Log Console UI
        log_handler = get_log_handler()
        log_handler.clear()

        st.markdown('<div class="terminal-title">Real-Time Terminal Activity</div>', unsafe_allow_html=True)
        log_placeholder = st.empty()

        async def _run_and_stream():
            pipeline_task = asyncio.create_task(
                run_pipeline_async(
                    country=country,
                    city=city,
                    property_type=prop_type if prop_type != "All" else None,
                    transaction_type=trans_type if trans_type != "All" else None,
                    max_sites_to_curate=max_curated,
                    max_pages_per_site=max_pages,
                    save_to_csv=True
                )
            )

            # Polling logs safely from main loop without thread conflicts
            while not pipeline_task.done():
                logs_text = log_handler.get_logs_as_text()
                if logs_text:
                    log_placeholder.markdown(
                        f'<div class="terminal-container">{logs_text}</div>',
                        unsafe_allow_html=True
                    )
                await asyncio.sleep(0.35)

            return await pipeline_task

        with st.spinner("Executing discovery and extraction pipeline..."):
            try:
                result = asyncio.run(_run_and_stream())

                # Final update of log window
                final_logs = log_handler.get_logs_as_text()
                if final_logs:
                    log_placeholder.markdown(
                        f'<div class="terminal-container">{final_logs}</div>',
                        unsafe_allow_html=True
                    )

                st.session_state["current_df"] = result.dataframe
                st.session_state["current_city"] = city
                st.session_state["curated_sites"] = result.curated_sites
                
                if getattr(result, "is_partial", False):
                    st.warning(
                        f"⚠️ **Partial Scraping Result**: API rate limit reached during execution, "
                        f"but **all {len(result.properties)} properties collected so far were successfully saved to history** "
                        f"(`{result.saved_file_path or 'data/processed/'}`) and are displayed in the table and charts below!"
                    )
                else:
                    st.success(f"Extraction completed successfully. **{len(result.properties)}** properties found.")

            except Exception as exc:
                final_logs = log_handler.get_logs_as_text()
                if final_logs:
                    log_placeholder.markdown(
                        f'<div class="terminal-container">{final_logs}</div>',
                        unsafe_allow_html=True
                    )
                st.error(f"Error during execution: {exc}")
                return

    # 5. Render Main Dashboard Content
    df: pd.DataFrame = st.session_state.get("current_df", pd.DataFrame())

    if not df.empty:
        # Curated sites tags
        curated_sites = st.session_state.get("curated_sites", [])
        if curated_sites:
            st.markdown(
                '<div style="margin-bottom: 14px; font-size: 13px;"><strong>AI Curated Portals:</strong> ' +
                " ".join([f'<span class="badge badge-gold">{site}</span>' for site in curated_sites]) +
                '</div>',
                unsafe_allow_html=True
            )

        # 5.1 KPI Cards
        render_metrics_cards(df)

        # 5.2 Tabs for Views (English)
        tab_table, tab_charts, tab_extra, tab_export = st.tabs([
            "Property Listings",
            "Metrics & Charts",
            "Extra Details",
            "Data Export"
        ])

        with tab_table:
            render_table_view(df)

        with tab_charts:
            render_charts_view(df)

        with tab_extra:
            render_extra_info_view(df)

        with tab_export:
            city_label = st.session_state.get("current_city") or "properties"
            render_export_buttons(df, city_name=city_label)

    else:
        # Minimalist Welcome State
        st.markdown(
            """
            <div style="text-align: center; padding: 48px 20px; background: #FFFFFF; 
                        border: 1px solid var(--border-card); border-radius: 12px; margin-top: 14px;">
                <h3 style="color: var(--color-olive-dark); margin: 0 0 6px 0; font-weight: 700; font-size: 18px;">Ready to start discovery</h3>
                <p style="color: var(--text-muted); max-width: 480px; margin: 0 auto; font-size: 13px;">
                    Select your country, city, and filters in the sidebar on the left and click 
                    <strong>Start Search & Extraction</strong>, or load a previous result from the search history.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()
