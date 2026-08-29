import time
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
from openai import OpenAI, RateLimitError, APIError

from config.settings import (
    LLM_API_KEY,
    LLM_MODEL,
    LLM_BASE_URL,
    LLM_TEMPERATURE,
    LLM_RATE_LIMIT_DELAY_SECONDS,
    LLM_MAX_RETRIES,
    PROMPTS_DIR,
)
from src.extractor.schemas import (
    PropertyListing,
    PropertyExtractionResult,
    CuratedSitesResult,
)

logger = logging.getLogger(__name__)

# Domains that are strictly non-real estate websites
DISALLOWED_DOMAINS = [
    "instagram.com",
    "facebook.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "pinterest.com",
    "tiktok.com",
    "wikipedia.org",
    "reddit.com",
    "globo.com",
    "uol.com.br",
    "estadao.com.br",
]


class LLMExtractionError(Exception):
    """Base exception for errors during LLM extraction."""
    pass


class MissingAPIKeyError(LLMExtractionError):
    """Raised when the LLM API key is not configured."""
    pass


class NoPropertiesExtractedError(LLMExtractionError):
    """Raised when the extraction yields zero properties across all visited sites."""
    pass


def _get_client(client: Optional[OpenAI] = None) -> OpenAI:
    """Returns an initialized OpenAI/Gemini client."""
    if client is not None:
        return client

    api_key = LLM_API_KEY
    if not api_key:
        raise MissingAPIKeyError(
            "LLM API Key (GEMINI_API_KEY or OPENAI_API_KEY) is not configured. "
            "Please configure your API key in the sidebar or in a .env file."
        )

    if LLM_BASE_URL:
        return OpenAI(api_key=api_key, base_url=LLM_BASE_URL)
    return OpenAI(api_key=api_key)


def _load_system_prompt(target_city: str, country: str = "Brasil") -> str:
    """Loads and formats the system prompt template with the target city and country."""
    prompt_file = PROMPTS_DIR / "extraction_system_prompt.txt"
    if prompt_file.exists():
        template = prompt_file.read_text(encoding="utf-8")
        return template.format(target_city=target_city, country=country)
    
    return (
        f"You are a real estate data extraction assistant. "
        f"Extract all property listings in '{target_city}', {country} from the following text into structured JSON. "
        f"Respond in the official language of {country}. Do not invent facts. Set missing fields to null."
    )


def curate_top_real_estate_sites(
    candidate_urls: List[str],
    target_city: str,
    country: str = "Brasil",
    max_sites: int = 2,
    client: Optional[OpenAI] = None
) -> List[str]:
    """
    Asks the LLM to inspect all discovered candidate URLs and return the exact
    original deep listing URLs for the top N most reputable portals in that country/region.
    Uses index-based matching to prevent the LLM from truncating deep paths to root domains.
    """
    if not candidate_urls:
        return []

    # 1. Filter out obvious non-property domains first
    clean_candidates: list[str] = []
    for u in candidate_urls:
        domain = urlparse(u).netloc.lower()
        if not any(disallowed in domain for disallowed in DISALLOWED_DOMAINS):
            clean_candidates.append(u)

    if len(clean_candidates) <= max_sites:
        return clean_candidates

    client_instance = _get_client(client)
    
    system_prompt = (
        f"You are an expert real estate researcher analyzing websites in {country}. "
        f"Your task is to analyze candidate search URLs for '{target_city}', {country} and select exactly "
        f"the top {max_sites} most reputable, established real estate listing portals or brokerages "
        f"that contain direct property listing search results for that location. "
        f"Return the 1-based integer indexes of the chosen items."
    )

    formatted_candidates = "\n".join(f"[{idx}] {url}" for idx, url in enumerate(clean_candidates, start=1))
    user_prompt = (
        f"Target Location: {target_city}, {country}\n"
        f"Required number of websites: {max_sites}\n\n"
        f"Candidate URLs:\n{formatted_candidates}\n\n"
        f"Select the top {max_sites} best indexes from the list."
    )

    logger.info(f"LLM Curating top {max_sites} deep URLs from {len(clean_candidates)} search candidates for {country}...")

    try:
        completion = client_instance.beta.chat.completions.parse(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=CuratedSitesResult,
            temperature=0.0,
        )
        parsed: CuratedSitesResult = completion.choices[0].message.parsed
        if parsed and parsed.selected_indexes:
            selected_urls: list[str] = []
            for index in parsed.selected_indexes:
                if 1 <= index <= len(clean_candidates):
                    selected_urls.append(clean_candidates[index - 1])

            if selected_urls:
                chosen = selected_urls[:max_sites]
                logger.info(f"Top {len(chosen)} deep URLs selected by AI: {chosen}")
                return chosen
    except Exception as exc:
        logger.warning(f"LLM curation notice ({exc}). Using top search candidates.")

    # Fallback: preserve exact deep paths of top N candidates
    return clean_candidates[:max_sites]


def extract_properties_from_text(
    cleaned_text: str,
    target_city: str,
    country: str = "Brasil",
    source_url: Optional[str] = None,
    client: Optional[OpenAI] = None
) -> List[PropertyListing]:
    """
    Extracts structured property listings from cleaned webpage text using Structured Outputs.
    Adapts language and localization according to the target country.
    """
    if not cleaned_text or not cleaned_text.strip():
        logger.info("Cleaned text is empty. Skipping LLM extraction.")
        return []

    client_instance = _get_client(client)
    system_prompt = _load_system_prompt(target_city=target_city, country=country)
    user_prompt = (
        f"Target Location: {target_city}, {country}\n"
        f"Source URL: {source_url or 'N/A'}\n\n"
        f"--- WEBPAGE TEXT CONTENT ---\n"
        f"{cleaned_text}\n"
        f"--- END OF TEXT CONTENT ---\n\n"
        f"Extract all property listings found above in the primary language of {country}."
    )

    if LLM_RATE_LIMIT_DELAY_SECONDS > 0:
        time.sleep(LLM_RATE_LIMIT_DELAY_SECONDS)

    logger.info(
        f"Invoking LLM ({LLM_MODEL}) for structured extraction in language of {country} "
        f"(Source: {source_url or 'Unknown'})..."
    )

    last_error: Optional[Exception] = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            completion = client_instance.beta.chat.completions.parse(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=PropertyExtractionResult,
                temperature=LLM_TEMPERATURE,
            )

            parsed_result: PropertyExtractionResult = completion.choices[0].message.parsed

            if not parsed_result or not parsed_result.properties:
                logger.info(f"LLM found 0 properties for location '{target_city}, {country}' on {source_url}.")
                return []

            for prop in parsed_result.properties:
                if not prop.source_url and source_url:
                    prop.source_url = source_url
                if not prop.city:
                    prop.city = target_city

            logger.info(f"Successfully extracted {len(parsed_result.properties)} properties from {source_url}.")
            return parsed_result.properties

        except (RateLimitError, APIError) as exc:
            last_error = exc
            error_msg = str(exc).lower()
            is_rate_limit = (
                "429" in error_msg
                or "rate limit" in error_msg
                or "quota" in error_msg
                or "resource_exhausted" in error_msg
                or "too many requests" in error_msg
                or "503" in error_msg
            )

            if is_rate_limit and attempt < LLM_MAX_RETRIES:
                backoff_seconds = (attempt * 6) + 2
                logger.warning(
                    f"API rate limit / 503 on attempt {attempt}/{LLM_MAX_RETRIES} for '{source_url}'. "
                    f"Waiting {backoff_seconds}s for cooldown before retrying..."
                )
                time.sleep(backoff_seconds)
            else:
                logger.error(f"API error on attempt {attempt}/{LLM_MAX_RETRIES} for {source_url}: {exc}")
                if attempt >= LLM_MAX_RETRIES:
                    break
        except Exception as exc:
            last_error = exc
            logger.error(f"Unexpected error during LLM extraction for {source_url}: {exc}")
            break

    raise LLMExtractionError(f"LLM extraction failed after {LLM_MAX_RETRIES} attempts: {last_error}")
