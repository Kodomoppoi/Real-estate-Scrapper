import os
import subprocess
import sys

if __name__ == "__main__":
    print("Rebuilding Standalone Executable with all dependencies bundled...")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name=RealEstateAI",
        "--add-data=app.py;.",
        "--add-data=frontend;frontend",
        "--add-data=prompts;prompts",
        "--add-data=config;config",
        "--add-data=src;src",
        "--add-data=.streamlit;.streamlit",
        "--copy-metadata=streamlit",
        "--copy-metadata=openai",
        "--copy-metadata=pydantic",
        "--copy-metadata=ddgs",
        "--collect-all=streamlit",
        "--collect-all=openai",
        "--collect-all=pydantic",
        "--collect-all=pydantic_core",
        "--collect-all=altair",
        "--collect-all=ddgs",
        "--collect-all=requests",
        "--collect-all=urllib3",
        "run.py"
    ]

    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\nBuild successfully generated in: dist\\RealEstateAI\\RealEstateAI.exe")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
