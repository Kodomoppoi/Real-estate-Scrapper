import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
BASE_DIR: Path = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppConfig:
    """
    Immutable, strictly-typed configuration container for the application.
    """
    base_dir: Path = BASE_DIR
    data_raw_dir: Path = BASE_DIR / "data" / "raw"
    data_processed_dir: Path = BASE_DIR / "data" / "processed"
    prompts_dir: Path = BASE_DIR / "prompts"

    # LLM Settings
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_api_key: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-3.6-flash")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    llm_rate_limit_delay_seconds: float = float(os.getenv("LLM_RATE_LIMIT_DELAY_SECONDS", "4.0"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "5"))
    llm_base_url: Optional[str] = (
        os.getenv("LLM_BASE_URL")
        or ("https://generativelanguage.googleapis.com/v1beta/openai/" if "gemini" in os.getenv("LLM_MODEL", "gemini").lower() else None)
    )

    # Scraper & Cleaner Settings
    cleaner_max_chars: int = int(os.getenv("CLEANER_MAX_CHARS", "15000"))
    default_max_pages_per_site: int = int(os.getenv("DEFAULT_MAX_PAGES_PER_SITE", "1"))
    crawler_timeout_seconds: int = int(os.getenv("CRAWLER_TIMEOUT_SECONDS", "30"))
    crawler_concurrency_limit: int = int(os.getenv("CRAWLER_CONCURRENCY_LIMIT", "3"))

    def initialize_directories(self) -> None:
        """Ensures all required local directories exist."""
        self.data_raw_dir.mkdir(parents=True, exist_ok=True)
        self.data_processed_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)


# Singleton Config Instance
config: AppConfig = AppConfig()
config.initialize_directories()

# Backward-compatible global exports
DATA_RAW_DIR = config.data_raw_dir
DATA_PROCESSED_DIR = config.data_processed_dir
PROMPTS_DIR = config.prompts_dir
GEMINI_API_KEY = config.gemini_api_key
OPENAI_API_KEY = config.openai_api_key
LLM_API_KEY = config.llm_api_key
LLM_MODEL = config.llm_model
LLM_TEMPERATURE = config.llm_temperature
LLM_RATE_LIMIT_DELAY_SECONDS = config.llm_rate_limit_delay_seconds
LLM_MAX_RETRIES = config.llm_max_retries
LLM_BASE_URL = config.llm_base_url
CLEANER_MAX_CHARS = config.cleaner_max_chars
DEFAULT_MAX_PAGES_PER_SITE = config.default_max_pages_per_site
CRAWLER_TIMEOUT_SECONDS = config.crawler_timeout_seconds
CRAWLER_CONCURRENCY_LIMIT = config.crawler_concurrency_limit
