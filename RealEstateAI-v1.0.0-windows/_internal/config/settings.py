import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# LLM Provider & API Keys (supports both Gemini and OpenAI)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_API_KEY = GEMINI_API_KEY or OPENAI_API_KEY or os.getenv("LLM_API_KEY", "")

# LLM Model & Base URL
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.6-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# Free-tier rate limiting and retry safeguards (15 RPM friendly)
LLM_RATE_LIMIT_DELAY_SECONDS = float(os.getenv("LLM_RATE_LIMIT_DELAY_SECONDS", "4.0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))

# Cleaner Token Optimization Settings
CLEANER_MAX_CHARS = int(os.getenv("CLEANER_MAX_CHARS", "15000"))

# Crawler & Pagination Settings
DEFAULT_MAX_PAGES_PER_SITE = int(os.getenv("DEFAULT_MAX_PAGES_PER_SITE", "1"))
CRAWLER_TIMEOUT_SECONDS = int(os.getenv("CRAWLER_TIMEOUT_SECONDS", "30"))
CRAWLER_CONCURRENCY_LIMIT = int(os.getenv("CRAWLER_CONCURRENCY_LIMIT", "3"))

# Automatically configure Base URL if using Gemini
configured_base_url = os.getenv("LLM_BASE_URL", "")
if not configured_base_url:
    if "gemini" in LLM_MODEL.lower() or LLM_API_KEY.startswith(("AQ.", "AQ-", "AIza")):
        configured_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

LLM_BASE_URL = configured_base_url or None

# Data Directories
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROMPTS_DIR = BASE_DIR / "prompts"

# Ensure data directories exist
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
