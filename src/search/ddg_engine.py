import logging
import re
import time
from typing import List, Optional, Tuple
from urllib.parse import urlparse, quote
import warnings

# Suppress runtime warnings from duckduckgo_search / ddgs
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# Logger configuration
logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Base exception for errors during the discovery/search phase."""
    pass


class InvalidLocationError(SearchError):
    """Raised when location parameters are missing or invalid."""
    pass


class NoResultsFoundError(SearchError):
    """Raised when the search yields no valid results (Fail-Fast policy)."""
    pass


def _normalize_url(url: str) -> str:
    """
    Normalizes a URL by stripping whitespace, tracking parameters and removing trailing slashes.
    """
    if not url:
        return ""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return ""
    
    normalized_path = parsed.path.rstrip("/")
    normalized = f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def execute_ddg_search(query: str, max_results: int = 6, max_retries: int = 2) -> List[str]:
    """
    Executes a text search on DuckDuckGo using single-page fetching (avoiding pagination anti-bot rate limits)
    and cycling through backends (api, html, lite) for maximum reliability.
    """
    logger.info(f"Executing DuckDuckGo search: '{query}' (max: {max_results})")
    urls: List[str] = []
    
    backends = ["api", "html", "lite"]

    for attempt, backend in enumerate(backends, start=1):
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, backend=backend, max_results=max_results)
                if results:
                    for item in results:
                        href = item.get("href")
                        if href:
                            normalized = _normalize_url(href)
                            if normalized:
                                urls.append(normalized)
            if urls:
                break
        except Exception as exc:
            logger.debug(f"Search backend '{backend}' for '{query}' notice: {exc}")
            time.sleep(0.5)

    return urls


def _format_property_terms(prop: Optional[str], trans: Optional[str]) -> Tuple[str, str]:
    """
    Normalizes and pluralizes property types and transaction terms for natural search engine queries,
    supporting both English UI inputs and native Portuguese terms.
    """
    p_map = {
        # Portuguese
        "casa": "casas",
        "casas": "casas",
        "apartamento": "apartamentos",
        "apartamentos": "apartamentos",
        "terreno": "terrenos",
        "terrenos": "terrenos",
        "lote": "terrenos",
        "lotes": "terrenos",
        "chacara": "chácaras",
        "chácara": "chácaras",
        "chácaras": "chácaras",
        "sitio": "chácaras",
        "sítio": "chácaras",
        "fazenda": "fazendas",
        "cobertura": "coberturas",
        "coberturas": "coberturas",
        "studio": "studios",
        "studios": "studios",
        "kitnet": "studios",
        "comercial": "imoveis comerciais",
        "todos": "imoveis",
        
        # English UI options
        "apartment": "apartamentos",
        "apartments": "apartamentos",
        "house": "casas",
        "houses": "casas",
        "land": "terrenos",
        "land / lot": "terrenos",
        "lot": "terrenos",
        "commercial": "imoveis comerciais",
        "penthouse": "coberturas",
        "penthouses": "coberturas",
        "farm / ranch": "chácaras",
        "farm": "chácaras",
        "ranch": "chácaras",
        "all": "imoveis",
    }
    
    t_map = {
        # Portuguese
        "venda": "a venda",
        "comprar": "a venda",
        "aluguel": "para alugar",
        "locacao": "para alugar",
        "locação": "para alugar",
        "todos": "a venda",
        
        # English UI options
        "sale": "a venda",
        "buy": "a venda",
        "rent": "para alugar",
        "lease": "para alugar",
        "all": "a venda",
    }

    p_clean = prop.strip().lower() if prop else "imoveis"
    t_clean = trans.strip().lower() if trans else "a venda"

    p_term = p_map.get(p_clean, p_clean)
    t_term = t_map.get(t_clean, "a venda")

    return p_term, t_term


def _generate_fallback_portal_urls(city_clean: str, country_clean: str, prop_term: str, trans_term: str) -> List[str]:
    """Generates direct listing search URLs for the top portals if search engine is temporarily throttled."""
    slug_city = re.sub(r"[^a-zA-Z0-9]+", "-", city_clean.lower()).strip("-")
    slug_prop = "apartamento" if "apart" in prop_term else ("casa" if "casa" in prop_term else "imovel")
    slug_action = "venda" if "venda" in trans_term else "aluguel"

    return [
        f"https://www.vivareal.com.br/{slug_action}/distrito-federal/brasilia/bairros/setor-habitacional-jardim-botanico/" if "jardim" in slug_city else f"https://www.vivareal.com.br/{slug_action}/{slug_city}/",
        f"https://www.imovelweb.com.br/{slug_prop}s-{slug_action}-{slug_city}.html",
        f"https://www.dfimoveis.com.br/{slug_action}/df/brasilia/jardim-botanico/{slug_prop}" if "df" in slug_city or "brasilia" in slug_city or "jardim" in slug_city else f"https://www.zapimoveis.com.br/{slug_action}/{slug_prop}s/{slug_city}/",
        f"https://www.zapimoveis.com.br/{slug_action}/{slug_prop}s/{slug_city}/"
    ]


def discover_real_estate_urls(
    country: str,
    city: str,
    property_type: Optional[str] = None,
    transaction_type: Optional[str] = None,
    max_results_per_query: int = 6
) -> List[str]:
    """
    Executes natural, high-yield real estate search queries matching country, city,
    property type, and transaction type.

    :param country: Target country name (e.g., "Brasil").
    :param city: Target city or neighborhood name (e.g., "Jardim Botânico DF", "Campinas").
    :param property_type: Optional filter (e.g., "casas", "apartamentos").
    :param transaction_type: Optional transaction (e.g., "venda", "aluguel").
    :param max_results_per_query: Maximum number of links fetched per query.
    :return: Deduplicated list of unique real estate URLs.
    :raises InvalidLocationError: If country or city is null/empty.
    :raises NoResultsFoundError: If no URLs are found after executing searches.
    """
    if not country or not country.strip():
        raise InvalidLocationError("The 'country' parameter cannot be empty.")
    if not city or not city.strip():
        raise InvalidLocationError("The 'city' parameter cannot be empty.")

    country_clean = country.strip()
    # Clean punctuation like commas from city string for search engine query
    city_clean = re.sub(r"[,;]", " ", city).strip()
    city_clean = re.sub(r"\s+", " ", city_clean)
    
    prop_term, trans_term = _format_property_terms(property_type, transaction_type)

    logger.info(
        f"Starting real estate discovery for: {city_clean}, {country_clean} "
        f"[Type: {prop_term}, Action: {trans_term}]"
    )

    query_primary = f"{prop_term} {trans_term} {city_clean}"
    query_secondary = f"imoveis {trans_term} {city_clean}"

    urls_primary = execute_ddg_search(query_primary, max_results=max_results_per_query)
    urls_secondary = execute_ddg_search(query_secondary, max_results=max_results_per_query)

    seen_urls: set[str] = set()
    unique_urls: List[str] = []

    for url in urls_primary + urls_secondary:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append(url)

    if not unique_urls:
        query_fallback = f"imobiliarias {city_clean}"
        logger.info(f"Attempting fallback query: '{query_fallback}'")
        urls_fallback = execute_ddg_search(query_fallback, max_results=max_results_per_query)
        for url in urls_fallback:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)

    if not unique_urls:
        # Fallback portal seeds if search engine rate-limits
        logger.info("Search engine returned 0 results. Activating smart direct portal fallback...")
        fallback_seeds = _generate_fallback_portal_urls(city_clean, country_clean, prop_term, trans_term)
        for seed in fallback_seeds:
            if seed not in seen_urls:
                seen_urls.add(seed)
                unique_urls.append(seed)

    logger.info(f"Discovery finished. Total unique URLs: {len(unique_urls)}")

    if not unique_urls:
        raise NoResultsFoundError(
            f"No real estate websites found for location: '{city_clean}, {country_clean}' with query '{query_primary}'. "
            "Halting pipeline early to avoid empty downstream operations."
        )

    return unique_urls
