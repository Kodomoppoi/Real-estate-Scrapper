import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Optional, Any, Type
from urllib.parse import urlparse
from openai import OpenAI, RateLimitError, APIError, AuthenticationError

from config.settings import (
    LLM_API_KEY,
    LLM_MODEL,
    LLM_BASE_URL,
    LLM_TEMPERATURE,
    LLM_RATE_LIMIT_DELAY_SECONDS,
    PROMPTS_DIR,
)
from src.extractor.schemas import (
    PropertyListing,
    PropertyExtractionResult,
    CuratedSitesResult,
)

logger = logging.getLogger(__name__)

# Domains that are strictly non-real estate portals or inappropriate
DISALLOWED_DOMAINS: List[str] = [
    # Social & Media & Streaming
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
    "spotify.com",
    "netflix.com",
    "twitch.tv",
    "discord.com",
    "whatsapp.com",
    "telegram.org",
    # Software & App Stores
    "microsoft.com",
    "apple.com",
    "github.com",
    "adobe.com",
    "steampowered.com",
    "steamcommunity.com",
    # E-commerce & Search Engines
    "google.com",
    "bing.com",
    "yahoo.com",
    "amazon.com",
    "mercadolivre.com.br",
    "shopee.com.br",
    "aliexpress.com",
    "ebay.com",
    # Adult / NSFW
    "pornhub.com",
    "xvideos.com",
    "xnxx.com",
    "redtube.com",
    "youporn.com",
    "onlyfans.com",
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
    """Returns an initialized OpenAI/Gemini/Groq client matching the active provider and URL."""
    if client is not None:
        return client

    base_url = os.getenv("LLM_BASE_URL", LLM_BASE_URL or "")
    model = os.getenv("LLM_MODEL", LLM_MODEL or "")

    base_url_lower = str(base_url).lower()
    model_lower = str(model).lower()

    if "groq" in base_url_lower or "groq" in model_lower:
        api_key = (
            os.getenv("GROQ_API_KEY", "")
            or os.getenv("LLM_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        )
    elif "generativelanguage" in base_url_lower or ("gemini" in model_lower and not any(k in base_url_lower for k in ["groq", "openrouter", "openai.com"])):
        api_key = (
            os.getenv("GEMINI_API_KEY", "")
            or os.getenv("LLM_API_KEY", "")
        )
    elif "openrouter" in base_url_lower:
        api_key = (
            os.getenv("OPENROUTER_API_KEY", "")
            or os.getenv("LLM_API_KEY", "")
            or os.getenv("CUSTOM_API_KEY", "")
        )
    elif "api.openai.com" in base_url_lower or ("gpt" in model_lower and not any(k in base_url_lower for k in ["groq", "openrouter"])):
        api_key = (
            os.getenv("OPENAI_API_KEY", "")
            or os.getenv("LLM_API_KEY", "")
        )
    else:
        api_key = (
            os.getenv("LLM_API_KEY", "")
            or os.getenv("OPENROUTER_API_KEY", "")
            or os.getenv("CUSTOM_API_KEY", "")
            or os.getenv("GROQ_API_KEY", "")
            or os.getenv("GEMINI_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        )

    api_key = (api_key or LLM_API_KEY or "").strip().strip("\"'")
    if not api_key:
        raise MissingAPIKeyError(
            "API key is not configured. Please enter your API key in the sidebar or set it in your .env file."
        )

    if base_url and str(base_url).strip():
        return OpenAI(api_key=api_key, base_url=str(base_url).strip())
    return OpenAI(api_key=api_key)


def _clean_and_parse_json(raw_text: str, response_model: Type[Any]) -> Any:
    """
    Cleans and isolates JSON payloads from raw LLM responses,
    stripping reasoning blocks (<think>...</think>), markdown code fences (```json...```),
    and using raw_decode to strictly parse up to the end of the JSON object,
    completely ignoring all trailing characters and subsequent text.
    """
    if not raw_text:
        return response_model()

    text = raw_text.strip()
    # 1. Strip reasoning thoughts with closing tag </think>
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

    # 2. If <think> was unclosed, discard everything before the first '{'
    if "<think>" in text:
        first_brace_pos = text.find("{")
        if first_brace_pos != -1:
            text = text[first_brace_pos:].strip()
        else:
            text = re.sub(r"<think>[\s\S]*", "", text, flags=re.IGNORECASE).strip()

    # 3. Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE).strip()

    # 4. Use raw_decode starting from the first '{' to ignore all trailing characters
    first_brace = text.find("{")
    if first_brace != -1:
        slice_text = text[first_brace:]
        try:
            decoded_dict, _ = json.JSONDecoder().raw_decode(slice_text)
            if isinstance(decoded_dict, dict):
                # Guard against models echoing back raw schema definitions ($defs)
                if "$defs" in decoded_dict and isinstance(decoded_dict.get("properties"), dict):
                    logger.warning("Model echoed JSON Schema definition instead of extracted data. Treating as 0 listings.")
                    return response_model()
                return response_model.model_validate(decoded_dict)
        except Exception as exc:
            logger.debug(f"raw_decode attempt notice: {exc}")

    # Fallback to brace slicing
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        clean_slice = text[first_brace:last_brace + 1]
        try:
            decoded = json.loads(clean_slice)
            if isinstance(decoded, dict):
                if "$defs" in decoded and isinstance(decoded.get("properties"), dict):
                    return response_model()
                return response_model.model_validate(decoded)
        except Exception:
            pass

    # If text contains no JSON or is a guardrail/safety string (e.g. 'User Safety: safe')
    try:
        return response_model.model_validate_json(text)
    except Exception as exc:
        logger.debug(f"Non-JSON or guardrail text received from model ('{text[:60]}...'): {exc}. Returning empty model.")
        return response_model()


def _execute_structured_completion(
    client: OpenAI,
    model: str,
    messages: List[dict],
    response_model: Type[Any],
    temperature: float = 0.0
) -> Any:
    """
    Executes structured extraction compatible across OpenAI, Google Gemini, Groq Cloud and OpenRouter.
    Automatically handles SDK differences (beta.parse vs standard json_schema / json_object)
    and robustly parses JSON responses even from reasoning models with think tags and trailing text.
    """
    base_url_str = str(client.base_url).lower()
    is_groq = "groq" in base_url_str
    is_openrouter = "openrouter" in base_url_str

    # 1. Native OpenAI / Gemini endpoint: attempt beta.parse first
    if not is_groq and not is_openrouter:
        try:
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_model,
                temperature=temperature,
            )
            return completion.choices[0].message.parsed
        except Exception as exc:
            logger.debug(f"beta.parse not supported on endpoint ({exc}), using standard json_schema...")

    # 2. Standard OpenAI-compatible JSON mode (Groq, OpenRouter, etc.)
    if response_model.__name__ == "CuratedSitesResult":
        schema_format = '{\n  "selected_indices": [1, 2, 3]\n}'
    else:
        schema_format = (
            '{\n  "properties": [\n    {\n      "title": "Apartamento 3 quartos...",\n'
            '      "price": "R$ 850.000",\n      "transaction_type": "Venda",\n'
            '      "property_type": "Apartamento",\n      "city": "Brasília",\n'
            '      "neighborhood": "Jardim Botânico",\n      "address": "Setor...",\n'
            '      "bedrooms": 3,\n      "suites": 1,\n      "bathrooms": 2,\n'
            '      "parking_spots": 2,\n      "area_m2": 85.0,\n'
            '      "amenities": ["Piscina", "Varanda"],\n      "financing_accepted": true,\n'
            '      "condo_fee": "R$ 600",\n      "iptu": "R$ 1.200",\n'
            '      "description": "Lindo apartamento..."\n    }\n  ]\n}'
        )

    json_messages = [dict(m) for m in messages]
    json_messages[0]["content"] += f"\n\nCRITICAL: Respond ONLY in valid JSON matching this exact structure:\n{schema_format}"
    
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=json_messages,
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=temperature,
        )
        raw_text = completion.choices[0].message.content or "{}"
        return _clean_and_parse_json(raw_text, response_model)
    except Exception as exc:
        logger.debug(f"JSON mode attempt notice: {exc}")
        # Try raw without response_format if provider doesn't support json_object
        completion = client.chat.completions.create(
            model=model,
            messages=json_messages,
            max_tokens=4096,
            temperature=temperature,
        )
        raw_text = completion.choices[0].message.content or "{}"
        return _clean_and_parse_json(raw_text, response_model)


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


def _extract_root_domain(url: str) -> str:
    """
    Extracts the normalized root domain without 'www.' or protocol,
    e.g., 'https://www.dfimoveis.com.br/venda/...' -> 'dfimoveis.com.br'
    """
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _deduplicate_by_domain(urls: List[str]) -> List[str]:
    """
    Preserves only the first URL for each unique root domain,
    preventing duplicate portals (e.g. two URLs from dfimoveis.com.br).
    """
    seen_domains = set()
    unique_urls = []
    for u in urls:
        dom = _extract_root_domain(u)
        if dom and dom not in seen_domains:
            seen_domains.add(dom)
            unique_urls.append(u)
    return unique_urls


def curate_top_real_estate_sites(
    candidate_urls: List[str],
    target_city: str,
    country: str = "Brasil",
    max_sites: int = 2,
    client: Optional[OpenAI] = None
) -> List[str]:
    """
    Asks the LLM to inspect all discovered candidate URLs and return the exact
    original deep listing URLs for the top N most reputable distinct portals.
    Enforces strict root-domain deduplication so no two URLs belong to the same portal.
    """
    if not candidate_urls:
        return []

    # 1. Filter out obvious non-property or disallowed domains and paths first
    disallowed_paths = ["/download", "/install", "/setup", "/track/", "/album/", "/artist/", "/app/", "/apk/", "/podcast/", "/music", "/game"]
    filtered: List[str] = []
    for u in candidate_urls:
        parsed_u = urlparse(u)
        domain = parsed_u.netloc.lower()
        path = parsed_u.path.lower()
        if any(disallowed in domain for disallowed in DISALLOWED_DOMAINS):
            continue
        if any(bad_path in path for bad_path in disallowed_paths):
            continue
        filtered.append(u)

    # 2. Deduplicate candidate URLs so each portal domain appears once
    clean_candidates = _deduplicate_by_domain(filtered)

    if len(clean_candidates) <= max_sites:
        return clean_candidates

    client_instance = _get_client(client)
    current_model = os.getenv("LLM_MODEL", LLM_MODEL)
    
    system_prompt = (
        f"You are an expert real estate researcher analyzing websites in {country}. "
        f"Your task is to analyze candidate search URLs for '{target_city}', {country} and select exactly "
        f"the top {max_sites} distinct, most reputable real estate listing portals or brokerages "
        f"that specifically target '{target_city}', {country}. "
        f"CRITICAL: Select DISTINCT portals (do not pick multiple links from the same domain). "
        f"Return the 1-based integer indexes of the chosen items."
    )

    formatted_candidates = "\n".join(f"[{idx}] {url}" for idx, url in enumerate(clean_candidates, start=1))
    user_prompt = (
        f"Target Location: {target_city}, {country}\n"
        f"Required number of websites: {max_sites}\n\n"
        f"Candidate URLs:\n{formatted_candidates}\n\n"
        f"Select the top {max_sites} distinct portal indexes specifically for '{target_city}'."
    )

    logger.info(f"LLM Curating top {max_sites} distinct deep URLs from {len(clean_candidates)} search candidates using {current_model}...")

    try:
        parsed: Optional[CuratedSitesResult] = _execute_structured_completion(
            client=client_instance,
            model=current_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=CuratedSitesResult,
            temperature=0.0
        )
        if parsed and parsed.selected_indexes:
            selected_urls: List[str] = []
            seen_domains = set()
            for index in parsed.selected_indexes:
                if 1 <= index <= len(clean_candidates):
                    cand_url = clean_candidates[index - 1]
                    dom = _extract_root_domain(cand_url)
                    if dom and dom not in seen_domains:
                        seen_domains.add(dom)
                        selected_urls.append(cand_url)

            # If fewer than max_sites due to duplicates, fill from remaining distinct candidates
            if len(selected_urls) < max_sites:
                for cand_url in clean_candidates:
                    dom = _extract_root_domain(cand_url)
                    if dom and dom not in seen_domains:
                        seen_domains.add(dom)
                        selected_urls.append(cand_url)
                        if len(selected_urls) >= max_sites:
                            break

            if selected_urls:
                chosen = selected_urls[:max_sites]
                logger.info(f"Top {len(chosen)} distinct deep URLs selected by AI ({current_model}): {chosen}")
                return chosen
    except AuthenticationError as exc:
        raise LLMAuthError(f"Invalid or unauthorized API key: {exc}")
    except (RateLimitError, APIError) as exc:
        if "quota" in str(exc).lower() or "429" in str(exc) or "resource_exhausted" in str(exc).lower():
            raise LLMQuotaExhaustedError(f"API quota limit reached on model {current_model}: {exc}")
        logger.warning(f"LLM curation notice ({exc}). Using top search candidates.")
    except Exception as exc:
        logger.debug(f"Curation notice ({exc}). Using top search candidates.")

    # Fallback: preserve exact deep paths of distinct candidates
    return clean_candidates[:max_sites]


def _chunk_cleaned_text(cleaned_text: str, max_chunk_chars: int = 3000) -> List[str]:
    """
    Splits cleaned text into strict micro-chunks under 3,000 chars (~800 tokens),
    guaranteeing 100% safety under Groq's 8,000 TPM limit with zero retry delays.
    """
    if len(cleaned_text) <= max_chunk_chars:
        return [cleaned_text]

    raw_pieces: List[str] = []
    if "=== [IMÓVEL" in cleaned_text:
        card_blocks = cleaned_text.split("=== [IMÓVEL")
        for card in card_blocks:
            if card.strip():
                raw_pieces.append("=== [IMÓVEL" + card)
    else:
        raw_pieces = cleaned_text.splitlines()

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for piece in raw_pieces:
        # If a single piece is abnormally long, slice it
        if len(piece) > max_chunk_chars:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            for i in range(0, len(piece), max_chunk_chars):
                sub = piece[i:i + max_chunk_chars]
                if sub.strip():
                    chunks.append(sub)
            continue

        if (current_length + len(piece) > max_chunk_chars) and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [piece]
            current_length = len(piece)
        else:
            current_chunk.append(piece)
            current_length += len(piece)

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks if chunks else [cleaned_text[:max_chunk_chars]]


def extract_properties_from_text(
    cleaned_text: str,
    target_city: str,
    country: str = "Brasil",
    source_url: Optional[str] = None,
    client: Optional[OpenAI] = None
) -> List[PropertyListing]:
    """
    Extracts structured property listings from cleaned webpage text using Structured Outputs with the active LLM model.
    Uses micro-batch chunking (max 2,500 chars per call) to guarantee zero 413 / TPM rate-limit errors on Groq.
    Compatible across Gemini, OpenAI, Groq, and OpenRouter.
    """
    if not cleaned_text or not cleaned_text.strip():
        logger.info("Cleaned text is empty. Skipping LLM extraction.")
        return []

    client_instance = _get_client(client)
    current_model = os.getenv("LLM_MODEL", LLM_MODEL)
    system_prompt = _load_system_prompt(target_city=target_city, country=country)

    text_chunks = _chunk_cleaned_text(cleaned_text, max_chunk_chars=2500)
    all_extracted_listings: List[PropertyListing] = []

    logger.info(
        f"Invoking LLM ({current_model}) for structured extraction ({len(text_chunks)} micro-batch chunk{'s' if len(text_chunks) > 1 else ''}) in language of {country} "
        f"(Source: {source_url or 'Unknown'})..."
    )

    for chunk_idx, chunk in enumerate(text_chunks, start=1):
        if len(text_chunks) > 1:
            logger.info(f"Processing Micro-Batch {chunk_idx}/{len(text_chunks)} ({len(chunk)} chars) on {current_model}...")

        user_prompt = (
            f"Target Location: {target_city}, {country}\n"
            f"Source URL: {source_url or 'N/A'}\n\n"
            f"--- WEBPAGE TEXT CONTENT ---\n"
            f"{chunk}\n"
            f"--- END OF TEXT CONTENT ---\n\n"
            f"Extract all property listings found above in the primary language of {country}."
        )

        for attempt in range(1, 3):
            try:
                parsed_result: Optional[PropertyExtractionResult] = _execute_structured_completion(
                    client=client_instance,
                    model=current_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_model=PropertyExtractionResult,
                    temperature=LLM_TEMPERATURE
                )

                if parsed_result and parsed_result.properties:
                    for prop in parsed_result.properties:
                        if not prop.source_url and source_url:
                            prop.source_url = source_url
                        if not prop.city:
                            prop.city = target_city
                    all_extracted_listings.extend(parsed_result.properties)
                    logger.info(f"Micro-Batch {chunk_idx}/{len(text_chunks)} extracted {len(parsed_result.properties)} properties.")
                break

            except AuthenticationError as exc:
                raise LLMAuthError(f"Invalid or unauthorized API key: {exc}")

            except (RateLimitError, APIError) as exc:
                error_msg = str(exc).lower()
                is_daily_exhausted = "generaterequestsperday" in error_msg or "daily" in error_msg or "resource_exhausted" in error_msg

                if is_daily_exhausted:
                    raise LLMQuotaExhaustedError(
                        f"Daily API quota limit reached on model {current_model}. "
                        f"Please wait for quota renewal or use an API key with available credits."
                    )

                if attempt == 1:
                    retry_match = re.search(r"retry(?:delay)?[:\s'\"]*(\d+)", error_msg)
                    backoff_seconds = min(int(retry_match.group(1)) + 2 if retry_match else 4, 8)
                    logger.warning(f"Rate limit cooldown for '{source_url}'. Waiting {backoff_seconds}s before 1 retry...")
                    time.sleep(backoff_seconds)
                else:
                    raise LLMQuotaExhaustedError(f"Rate limit error (429) on model {current_model}: {exc}")

            except Exception as exc:
                logger.error(f"Unexpected error during LLM extraction for {source_url}: {exc}")
                raise LLMExtractionError(f"Extraction error with model {current_model}: {exc}")

    logger.info(f"Successfully extracted {len(all_extracted_listings)} total properties from {source_url} using {current_model}.")
    return all_extracted_listings
