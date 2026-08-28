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


def _get_client(client: Optional[OpenAI] = None) -> OpenAI:
    """Returns an initialized OpenAI/Gemini client."""
    if client is not None:
        return client

    api_key = LLM_API_KEY
    if not api_key:
        raise MissingAPIKeyError(
            "LLM API Key (GEMINI_API_KEY or OPENAI_API_KEY) is not configured. "
            "Please create a .env file with your key (e.g., GEMINI_API_KEY=your_key)."
        )

    if LLM_BASE_URL:
        return OpenAI(api_key=api_key, base_url=LLM_BASE_URL)
    return OpenAI(api_key=api_key)


def _load_system_prompt(target_city: str) -> str:
    """Loads and formats the system prompt template with the target city."""
    prompt_file = PROMPTS_DIR / "extraction_system_prompt.txt"
    if prompt_file.exists():
        template = prompt_file.read_text(encoding="utf-8")
        return template.format(target_city=target_city)
    
    return (
        f"You are a real estate data extraction assistant. "
        f"Extract all property listings in '{target_city}' from the following text into structured JSON. "
        f"Do not invent facts. Set missing fields to null."
    )


def curate_top_real_estate_sites(
    candidate_urls: List[str],
    target_city: str,
    max_sites: int = 2,
    client: Optional[OpenAI] = None
) -> List[str]:
    """
    Asks the LLM to inspect all discovered candidate URLs at once and select the top N
    most famous, established, and relevant real estate portals/brokers for the city.

    :param candidate_urls: List of all candidate URLs found by the search engine.
    :param target_city: Target city or location.
    :param max_sites: Number of top sites to select (e.g., 2, 3, 5).
    :param client: Optional pre-configured OpenAI client.
    :return: List of top N curated URLs.
    """
    if not candidate_urls:
        return []

    # Filter out obvious non-property domains first
    clean_candidates: list[str] = []
    for u in candidate_urls:
        domain = urlparse(u).netloc.lower()
        if not any(disallowed in domain for disallowed in DISALLOWED_DOMAINS):
            clean_candidates.append(u)

    if len(clean_candidates) <= max_sites:
        return clean_candidates

    client_instance = _get_client(client)
    
    system_prompt = (
        f"You are a real estate market intelligence assistant. "
        f"Your task is to analyze candidate website URLs found for '{target_city}' and select exactly "
        f"the top {max_sites} most reputable, famous, and relevant real estate listing portals or local brokerages "
        f"(e.g., DFImoveis, Wimoveis, ZapImoveis, VivaReal, Imovelweb, local real estate agencies) that actually contain property listings. "
        f"Strictly exclude social media profiles, news blogs, forum links, or directory aggregators."
    )

    formatted_candidates = "\n".join(f"- {url}" for url in clean_candidates)
    user_prompt = (
        f"Target City: {target_city}\n"
        f"Required number of top websites: {max_sites}\n\n"
        f"Candidate URLs:\n{formatted_candidates}\n\n"
        f"Select the top {max_sites} best real estate websites."
    )

    logger.info(f"🤖 LLM Curating top {max_sites} websites from {len(clean_candidates)} search candidates...")

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
        if parsed and parsed.selected_urls:
            valid_selected = [u for u in parsed.selected_urls if u in clean_candidates or u.startswith("http")]
            if valid_selected:
                logger.info(f"Top {len(valid_selected[:max_sites])} websites curated: {valid_selected[:max_sites]}")
                return valid_selected[:max_sites]
    except Exception as exc:
        logger.warning(f"LLM curation warning ({exc}). Falling back to top search candidates.")

    # Fallback to top N clean candidates
    return clean_candidates[:max_sites]


def extract_properties_from_text(
    cleaned_text: str,
    target_city: str,
    source_url: Optional[str] = None,
    client: Optional[OpenAI] = None
) -> List[PropertyListing]:
    """
    Extracts structured property listings from cleaned webpage text using Structured Outputs.
    Features automated Rate-Limiting and Exponential Backoff for Gemini Free-Tier stability.
    """
    if not cleaned_text or not cleaned_text.strip():
        logger.info("Cleaned text is empty. Skipping LLM extraction.")
        return []

    client_instance = _get_client(client)
    system_prompt = _load_system_prompt(target_city=target_city)
    user_prompt = (
        f"Target City: {target_city}\n"
        f"Source URL: {source_url or 'N/A'}\n\n"
        f"--- WEBPAGE TEXT CONTENT ---\n"
        f"{cleaned_text}\n"
        f"--- END OF TEXT CONTENT ---\n\n"
        f"Extract all property listings found above."
    )

    if LLM_RATE_LIMIT_DELAY_SECONDS > 0:
        time.sleep(LLM_RATE_LIMIT_DELAY_SECONDS)

    logger.info(
        f"Invoking LLM ({LLM_MODEL}) for structured extraction "
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
                logger.info(f"LLM found 0 properties for city '{target_city}' on {source_url}.")
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
            )

            if is_rate_limit and attempt < LLM_MAX_RETRIES:
                backoff_seconds = (attempt * 6) + 2
                logger.warning(
                    f"Gemini Free-Tier rate limit (429) on attempt {attempt}/{LLM_MAX_RETRIES} for '{source_url}'. "
                    f"Waiting {backoff_seconds}s for quota cooldown before retrying..."
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
