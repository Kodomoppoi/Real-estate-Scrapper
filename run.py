import os
import sys
import subprocess

if __name__ == "__main__":
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller packaged standalone mode
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Auto-activate .venv if running outside the virtual environment
        venv_dir = os.path.join(base_dir, ".venv")
        venv_python = (
            os.path.join(venv_dir, "Scripts", "python.exe")
            if os.name == "nt"
            else os.path.join(venv_dir, "bin", "python")
        )
        if os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
            # Re-spawn process using the local virtual environment Python
            sys.exit(subprocess.call([venv_python, os.path.abspath(__file__)] + sys.argv[1:]))

    # Explicitly import all project modules for PyInstaller bundling & runtime
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
