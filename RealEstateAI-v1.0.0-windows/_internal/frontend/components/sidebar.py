import os
from pathlib import Path
from typing import Dict, Any, Optional
import streamlit as st
import pandas as pd
from openai import OpenAI

from config.settings import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, DATA_PROCESSED_DIR


def _test_llm_connection(api_key: str, model_name: str, base_url: Optional[str] = None) -> bool:
    """Tests if the provided LLM credentials and endpoint work properly."""
    try:
        kwargs = {"api_key": api_key.strip()}
        if base_url:
            kwargs["base_url"] = base_url.strip()
        client = OpenAI(**kwargs)
        client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1
        )
        return True
    except Exception:
        return False


def render_sidebar() -> Dict[str, Any]:
    """
    Renders the sidebar controls in English with custom defaults.
    """
    st.sidebar.markdown(
        """
        <div style="padding: 6px 0 14px 0;">
            <h2 style="color: #807454; margin: 0; font-weight: 800; font-size: 18px; letter-spacing: -0.3px;">Real Estate Scraper & AI</h2>
            <p style="color: #8D93AA; font-size: 12px; margin: 2px 0 0 0;">Discovery & Extraction Pipeline</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Multi-Provider API Configuration
    with st.sidebar.expander("AI Provider & API Key", expanded=False):
        provider_options = ["Google Gemini (Free)", "OpenAI (GPT-4o-mini)", "Custom / OpenRouter"]
        selected_provider = st.selectbox("AI Provider:", provider_options, index=0)

        if selected_provider == "Google Gemini (Free)":
            default_model = "gemini-3.6-flash"
            default_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            key_placeholder = "AIzaSy..."
        elif selected_provider == "OpenAI (GPT-4o-mini)":
            default_model = "gpt-4o-mini"
            default_url = "https://api.openai.com/v1"
            key_placeholder = "sk-..."
        else:
            default_model = "meta-llama/llama-3.3-70b-instruct"
            default_url = "https://openrouter.ai/api/v1"
            key_placeholder = "sk-or-..."

        current_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or LLM_API_KEY or ""
        input_key = st.text_input(
            "API Key:",
            value=current_key,
            type="password",
            placeholder=key_placeholder,
            help="Your API key for the chosen provider"
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            test_btn = st.button("Test Key", use_container_width=True)
        with col_btn2:
            save_env = st.checkbox("Save to .env", value=True)

        if test_btn:
            if not input_key.strip():
                st.error("Please enter a valid API key.")
            else:
                with st.spinner("Testing connection..."):
                    if _test_llm_connection(input_key, default_model, default_url):
                        os.environ["LLM_MODEL"] = default_model
                        os.environ["LLM_BASE_URL"] = default_url
                        if "gemini" in default_model:
                            os.environ["GEMINI_API_KEY"] = input_key.strip()
                        else:
                            os.environ["OPENAI_API_KEY"] = input_key.strip()

                        st.session_state["active_api_key"] = input_key.strip()
                        st.session_state["active_model"] = default_model
                        st.session_state["active_base_url"] = default_url
                        st.success(f"Connected: {default_model}")

                        if save_env:
                            env_path = Path(".env")
                            if "gemini" in default_model:
                                env_content = f'GEMINI_API_KEY="{input_key.strip()}"\nLLM_MODEL={default_model}\nLLM_BASE_URL={default_url}\n'
                            else:
                                env_content = f'OPENAI_API_KEY="{input_key.strip()}"\nLLM_MODEL={default_model}\nLLM_BASE_URL={default_url}\n'
                            env_path.write_text(env_content, encoding="utf-8")
                    else:
                        st.error("Connection failed. Check credentials.")

    # Status Indicator
    active_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or LLM_API_KEY or ""
    active_model = os.getenv("LLM_MODEL", LLM_MODEL)
    if active_key:
        st.sidebar.markdown(
            f"""
            <div style="background: #F4F8F0; border: 1px solid #D1E5C6; color: #2B5718; 
                        padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; 
                        margin-bottom: 16px; text-align: center;">
                API Active: {active_model}
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.warning("Configure the API Key above.")

    st.sidebar.markdown("### Search Parameters")

    # Initial defaults: Brasil & Ipanema Rio de Janeiro
    country = st.sidebar.text_input("Country", value="Brasil")
    city = st.sidebar.text_input("City / Neighborhood", value="Ipanema, Rio de Janeiro")

    prop_types = ["All", "Apartment", "House", "Land / Lot", "Commercial", "Penthouse", "Studio", "Farm / Ranch"]
    selected_prop_type = st.sidebar.selectbox("Property Type", prop_types, index=1)

    trans_types = ["Sale", "Rent", "All"]
    selected_trans_type = st.sidebar.selectbox("Transaction Type", trans_types, index=0)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### AI & Crawl Settings")

    max_curated = st.sidebar.slider(
        "AI Curated Sites",
        min_value=1,
        max_value=20,
        value=3,
        help="Number of top reputable real estate portals selected by AI (up to 20)."
    )

    max_pages = st.sidebar.slider(
        "Pages per Site",
        min_value=1,
        max_value=10,
        value=1,
        help="Consecutive listing pages to crawl per portal (up to 10)."
    )

    start_search = st.sidebar.button("Start Search & Extraction", use_container_width=True)

    # History of past processed CSV files
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Search History")

    saved_csvs = list(DATA_PROCESSED_DIR.glob("properties_*.csv"))
    selected_history_file: Optional[Path] = None

    if saved_csvs:
        csv_options = {f.name: f for f in sorted(saved_csvs, key=os.path.getmtime, reverse=True)}
        chosen_file_name = st.sidebar.selectbox(
            "Load previous search:",
            options=["Select a file..."] + list(csv_options.keys()),
            index=0
        )
        if chosen_file_name != "Select a file...":
            selected_history_file = csv_options[chosen_file_name]
    else:
        st.sidebar.caption("No previous results found.")

    return {
        "country": country,
        "city": city,
        "property_type": selected_prop_type,
        "transaction_type": selected_trans_type,
        "max_curated_sites": max_curated,
        "max_pages_per_site": max_pages,
        "start_search": start_search,
        "selected_history_file": selected_history_file
    }
