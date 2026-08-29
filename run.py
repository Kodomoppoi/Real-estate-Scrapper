import os
import sys

# Explicitly import all project modules so PyInstaller bundles every dependency
import openai
import pydantic
import requests
import urllib3
import pandas
import ddgs
import streamlit
from streamlit.web import cli as stcli

import config.settings
import src.pipeline
import src.search
import src.scraper
import src.extractor
import frontend.components
import frontend.utils

if __name__ == "__main__":
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_dir, "app.py")

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false"
    ]
    sys.exit(stcli.main())
