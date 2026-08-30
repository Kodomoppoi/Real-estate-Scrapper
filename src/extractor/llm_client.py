import re
import time
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
from openai import OpenAI, RateLimitError, APIError, AuthenticationError

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

# Domains that are strictly non-real estate portals
DISALLOWED_DOMAINS: List[str] = [
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


class LLMQuotaExhaustedError(LLMExtractionError):
    """Raised when API quota / credits are exhausted."""
    pass


class LLMAuthError(LLMExtractionError):
    """Raised when the API key is invalid or unauthorized."""
    pass


class NoPropertiesExtractedError(LLMExtractionError):
    """Raised when the extraction yields zero properties across all visited sites."""
    pass


def _get_client(client: Optional[OpenAI] = None) -> OpenAI:
    """Returns an initialized OpenAI/Gemini client."""
    if client is not None:
        return client

    api_key = (
        os.getenv("GEMINI_API_KEY", "")
        or os.getenv("OPENAI_API_KEY", "")
        or os.getenv("LLM_API_KEY", "")
        or (LLM_API_KEY if LLM_API_KEY else "")
    )
    api_key = api_key.strip().strip("\"'")
    if not api_key:
        raise MissingAPIKeyError(
            "Chave de API não configurada. Por favor, insira sua chave no menu lateral ou no arquivo .env."
        )

    base_url = os.getenv("LLM_BASE_URL", LLM_BASE_URL)
    if base_url and base_url.strip():
        return OpenAI(api_key=api_key, base_url=base_url.strip())
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
    clean_candidates: List[str] = []
    for u in candidate_urls:
        domain = urlparse(u).netloc.lower()
        if not any(disallowed in domain for disallowed in DISALLOWED_DOMAINS):
            clean_candidates.append(u)

    if len(clean_candidates) <= max_sites:
        return clean_candidates

    client_instance = _get_client(client)
    current_model = os.getenv("LLM_MODEL", LLM_MODEL)
    
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

    logger.info(f"LLM Curating top {max_sites} deep URLs from {len(clean_candidates)} search candidates using {current_model}...")

    try:
        completion = client_instance.beta.chat.completions.parse(
            model=current_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=CuratedSitesResult,
            temperature=0.0,
        )
        parsed: Optional[CuratedSitesResult] = completion.choices[0].message.parsed
        if parsed and parsed.selected_indexes:
            selected_urls: List[str] = []
            for index in parsed.selected_indexes:
                if 1 <= index <= len(clean_candidates):
                    selected_urls.append(clean_candidates[index - 1])

            if selected_urls:
                chosen = selected_urls[:max_sites]
                logger.info(f"Top {len(chosen)} deep URLs selected by AI ({current_model}): {chosen}")
                return chosen
    except AuthenticationError as exc:
        raise LLMAuthError(f"Chave de API inválida ou não autorizada: {exc}")
    except (RateLimitError, APIError) as exc:
        if "quota" in str(exc).lower() or "429" in str(exc) or "resource_exhausted" in str(exc).lower():
            raise LLMQuotaExhaustedError(f"Limite de cota da API atingido no modelo {current_model}: {exc}")
        logger.warning(f"LLM curation notice ({exc}). Using top search candidates.")
    except Exception as exc:
        logger.debug(f"Curation notice ({exc}). Using top search candidates.")

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
    Extracts structured property listings from cleaned webpage text using Structured Outputs with the active LLM model.
    Fails fast immediately if quota or authentication errors occur.
    """
    if not cleaned_text or not cleaned_text.strip():
        logger.info("Cleaned text is empty. Skipping LLM extraction.")
        return []

    client_instance = _get_client(client)
    current_model = os.getenv("LLM_MODEL", LLM_MODEL)
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
        f"Invoking LLM ({current_model}) for structured extraction in language of {country} "
        f"(Source: {source_url or 'Unknown'})..."
    )

    for attempt in range(1, 3):
        try:
            completion = client_instance.beta.chat.completions.parse(
                model=current_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=PropertyExtractionResult,
                temperature=LLM_TEMPERATURE,
            )

            parsed_result: Optional[PropertyExtractionResult] = completion.choices[0].message.parsed

            if not parsed_result or not parsed_result.properties:
                logger.info(f"LLM ({current_model}) found 0 properties for location '{target_city}, {country}' on {source_url}.")
                return []

            for prop in parsed_result.properties:
                if not prop.source_url and source_url:
                    prop.source_url = source_url
                if not prop.city:
                    prop.city = target_city

            logger.info(f"Successfully extracted {len(parsed_result.properties)} properties from {source_url} using {current_model}.")
            return parsed_result.properties

        except AuthenticationError as exc:
            # Invalid API key: abort immediately
            raise LLMAuthError(f"Chave de API inválida ou sem permissão: {exc}")

        except (RateLimitError, APIError) as exc:
            error_msg = str(exc).lower()
            is_daily_exhausted = "generaterequestsperday" in error_msg or "daily" in error_msg or "resource_exhausted" in error_msg

            if is_daily_exhausted:
                # Quota exhausted: abort immediately without endless waiting
                raise LLMQuotaExhaustedError(
                    f"Cota diária da API atingida no modelo {current_model}. "
                    f"Por favor, aguarde a renovação da cota do Google ou use uma chave com saldo."
                )

            if attempt == 1:
                retry_match = re.search(r"retry(?:delay)?[:\s'\"]*(\d+)", error_msg)
                backoff_seconds = min(int(retry_match.group(1)) + 2 if retry_match else 6, 12)
                logger.warning(f"Rate limit cooldown for '{source_url}'. Waiting {backoff_seconds}s before 1 retry...")
                time.sleep(backoff_seconds)
            else:
                raise LLMQuotaExhaustedError(f"Erro de taxa de requisições (429) no modelo {current_model}: {exc}")

        except Exception as exc:
            logger.error(f"Unexpected error during LLM extraction for {source_url}: {exc}")
            raise LLMExtractionError(f"Falha na extração com o modelo {current_model}: {exc}")

    raise LLMExtractionError(f"Falha na extração com o modelo {current_model}.")
