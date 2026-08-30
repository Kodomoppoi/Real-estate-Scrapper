import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import streamlit as st
import pandas as pd
from openai import OpenAI

from config.settings import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, DATA_PROCESSED_DIR


def _test_llm_connection(api_key: str, model_name: str, base_url: Optional[str] = None) -> Tuple[bool, str]:
    """Tests if the provided LLM credentials and endpoint work properly."""
    try:
        clean_key = api_key.strip().strip("\"'")
        kwargs: Dict[str, Any] = {"api_key": clean_key}
        if base_url and base_url.strip():
            kwargs["base_url"] = base_url.strip()
        client = OpenAI(**kwargs)
        client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=2
        )
        return True, "OK"
    except Exception as exc:
        return False, str(exc)


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

    # Initialize provider key states if not present
    if "gemini_key" not in st.session_state:
        st.session_state["gemini_key"] = os.getenv("GEMINI_API_KEY", "") or (LLM_API_KEY if "gemini" in LLM_MODEL.lower() else "")
    if "openai_key" not in st.session_state:
        st.session_state["openai_key"] = os.getenv("OPENAI_API_KEY", "") or (LLM_API_KEY if "gpt" in LLM_MODEL.lower() else "")
    if "custom_key" not in st.session_state:
        st.session_state["custom_key"] = os.getenv("CUSTOM_API_KEY", "")

    # Multi-Provider API Configuration
    with st.sidebar.expander("AI Provider & API Key", expanded=True if not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY") else False):
        provider_options = ["Google Gemini (Free)", "OpenAI (GPT-4o-mini)", "Custom / OpenRouter / Groq"]
        
        # Determine current provider index
        current_model = os.getenv("LLM_MODEL", LLM_MODEL)
        default_idx = 0
        if "gpt" in current_model.lower():
            default_idx = 1
        elif "openrouter" in str(os.getenv("LLM_BASE_URL", "")).lower() or "groq" in str(os.getenv("LLM_BASE_URL", "")).lower() or "llama" in current_model.lower():
            default_idx = 2

        selected_provider = st.selectbox("AI Provider:", provider_options, index=default_idx)

        if selected_provider == "Google Gemini (Free)":
            active_model = "gemini-3.6-flash"
            active_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            key_placeholder = "AIzaSy..."
            provider_stored_key = st.session_state["gemini_key"]
        elif selected_provider == "OpenAI (GPT-4o-mini)":
            active_model = "gpt-4o-mini"
            active_url = "https://api.openai.com/v1"
            key_placeholder = "sk-..."
            provider_stored_key = st.session_state["openai_key"]
        else:
            active_model = st.text_input("Model ID:", value=os.getenv("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct"), help="e.g. meta-llama/llama-3.3-70b-instruct or llama-3.3-70b-versatile")
            active_url = st.text_input("Base URL:", value=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"))
            key_placeholder = "sk-or-... or gsk_..."
            provider_stored_key = st.session_state["custom_key"]

        input_key = st.text_input(
            "API Key:",
            value=provider_stored_key,
            type="password",
            placeholder=key_placeholder,
            key=f"api_key_input_{selected_provider}",
            help="Your API key for the chosen provider"
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            save_btn = st.button("Save & Activate", use_container_width=True, type="primary")
        with col_btn2:
            test_btn = st.button("Test Key", use_container_width=True)

        if save_btn or (input_key.strip() and input_key.strip() != provider_stored_key):
            clean_key = input_key.strip().strip("\"'")
            if selected_provider == "Google Gemini (Free)":
                st.session_state["gemini_key"] = clean_key
                os.environ["GEMINI_API_KEY"] = clean_key
            elif selected_provider == "OpenAI (GPT-4o-mini)":
                st.session_state["openai_key"] = clean_key
                os.environ["OPENAI_API_KEY"] = clean_key
            else:
                st.session_state["custom_key"] = clean_key

            os.environ["LLM_API_KEY"] = clean_key
            os.environ["LLM_MODEL"] = active_model
            os.environ["LLM_BASE_URL"] = active_url

            # Save clean .env without quotes
            env_path = Path(".env")
            if selected_provider == "Google Gemini (Free)":
                env_content = f"GEMINI_API_KEY={clean_key}\nLLM_MODEL={active_model}\nLLM_BASE_URL={active_url}\n"
            elif selected_provider == "OpenAI (GPT-4o-mini)":
                env_content = f"OPENAI_API_KEY={clean_key}\nLLM_MODEL={active_model}\nLLM_BASE_URL={active_url}\n"
            else:
                env_content = f"LLM_API_KEY={clean_key}\nLLM_MODEL={active_model}\nLLM_BASE_URL={active_url}\n"
            env_path.write_text(env_content, encoding="utf-8")
            if save_btn:
                st.success("API Key activated and saved to .env!")

        if test_btn:
            clean_key = input_key.strip().strip("\"'")
            if not clean_key:
                st.error("Please enter an API key to test.")
            else:
                with st.spinner("Testing connection..."):
                    success, error_msg = _test_llm_connection(clean_key, active_model, active_url)
                    if success:
                        st.success(f"Connection Successful! Model: {active_model}")
                    else:
                        st.error(f"Connection Failed: {error_msg}")

    # Status Indicator
    active_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or os.getenv("LLM_API_KEY", "") or LLM_API_KEY or ""
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
        st.sidebar.warning("Configure your API Key above.")

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
        help="Number of pagination pages to crawl per portal (up to 10)."
    )

    # History Selector
    st.sidebar.markdown("---")
    st.sidebar.markdown("### History & Offline Mode")
    history_files = list(DATA_PROCESSED_DIR.glob("properties_*.csv"))
    history_options = ["None (Run Live Scrape)"] + [f.name for f in history_files]
    selected_history = st.sidebar.selectbox("Load previous search:", history_options, index=0)

    selected_history_file = None
    if selected_history != "None (Run Live Scrape)":
        selected_history_file = DATA_PROCESSED_DIR / selected_history

    # Start Scraping Button
    st.sidebar.markdown("---")
    start_clicked = st.sidebar.button(
        "Extract Listings",
        type="primary",
        use_container_width=True,
        disabled=(selected_history != "None (Run Live Scrape)")
    )

    return {
        "country": country,
        "city": city,
        "property_type": selected_prop_type if selected_prop_type != "All" else None,
        "transaction_type": selected_trans_type if selected_trans_type != "All" else None,
        "max_curated_sites": max_curated,
        "max_pages_per_site": max_pages,
        "start_clicked": start_clicked,
        "selected_history_file": selected_history_file
    }
