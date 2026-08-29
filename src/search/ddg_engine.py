import logging
from typing import Optional
from urllib.parse import urlparse

import warnings

# Suppress runtime warning from deprecated duckduckgo_search package
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*renamed to `ddgs`.*")

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
    Normalizes a URL by stripping whitespace and removing trailing slashes.
    """
    if not url:
        return ""
    parsed = urlparse(url.strip())
    # Keep only valid HTTP/HTTPS schemes
    if parsed.scheme not in ("http", "https"):
        return ""
    
    # Reconstruct normalized URL
    normalized_path = parsed.path.rstrip("/")
    normalized = f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def execute_ddg_search(query: str, max_results: int = 5) -> list[str]:
    """
    Executes a text search on DuckDuckGo and returns a list of discovered URLs.
    
    :param query: Search query string.
    :param max_results: Maximum number of results to fetch per search.
    :return: List of discovered URLs.
    """
    logger.info(f"Executing DuckDuckGo search: '{query}' (max: {max_results})")
    urls: list[str] = []
    
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            if results:
                for item in results:
                    href = item.get("href")
                    if href:
                        normalized = _normalize_url(href)
                        if normalized:
                            urls.append(normalized)
    except Exception as exc:
        logger.warning(f"Warning during search for query '{query}': {exc}")
    
    return urls


def _format_property_terms(prop: Optional[str], trans: Optional[str]) -> tuple[str, str]:
    """
    Normalizes and pluralizes property types and transaction terms for natural search engine queries.
    """
    p_map = {
        "casa": "casas",
        "apartamento": "apartamentos",
        "terreno": "terrenos",
        "chacara": "chácaras",
        "chácara": "chácaras",
        "cobertura": "coberturas",
        "studio": "studios",
        "comercial": "imoveis comerciais",
        "todos": "imóveis",
        "all": "imóveis",
    }
    
    t_map = {
        "venda": "a venda",
        "comprar": "a venda",
        "aluguel": "para alugar",
        "locacao": "para alugar",
        "locação": "para alugar",
        "todos": "a venda e aluguel",
    }

    p_clean = prop.strip().lower() if prop else "imoveis"
    t_clean = trans.strip().lower() if trans else "a venda"

    p_term = p_map.get(p_clean, p_clean)
    t_term = t_map.get(t_clean, "a venda")

    return p_term, t_term


def discover_real_estate_urls(
    country: str,
    city: str,
    property_type: Optional[str] = None,
    transaction_type: Optional[str] = None,
    max_results_per_query: int = 5
) -> list[str]:
    """
    Executes natural, high-yield real estate search queries matching country, city,
    property type (e.g., Casas, Apartamentos), and transaction type (e.g., A Venda, Para Alugar).

    :param country: Target country name (e.g., "Brasil").
    :param city: Target city or neighborhood name (e.g., "Jardim Botânico DF", "Campinas").
    :param property_type: Optional filter (e.g., "casas", "apartamentos").
    :param transaction_type: Optional transaction (e.g., "venda", "aluguel").
    :param max_results_per_query: Maximum number of links fetched per query.
    :return: Deduplicated list of unique real estate URLs.
    :raises InvalidLocationError: If country or city is null/empty.
    :raises NoResultsFoundError: If no URLs are found after executing searches.
    """
    # 1. Fail-Fast Input Validation
    if not country or not country.strip():
        raise InvalidLocationError("The 'country' parameter cannot be empty.")
    if not city or not city.strip():
        raise InvalidLocationError("The 'city' parameter cannot be empty.")

    country_clean = country.strip()
    city_clean = city.strip()
    
    prop_term, trans_term = _format_property_terms(property_type, transaction_type)

    logger.info(
        f"Starting real estate discovery for: {city_clean}, {country_clean} "
        f"[Type: {prop_term}, Action: {trans_term}]"
    )

    # 2. Build Natural Queries Targeting Direct Listing Pages
    query_primary = f"{prop_term} {trans_term} em {city_clean}"
    query_secondary = f"imoveis {trans_term} em {city_clean} {country_clean}"

    # 3. Execute Searches
    urls_primary = execute_ddg_search(query_primary, max_results=max_results_per_query)
    urls_secondary = execute_ddg_search(query_secondary, max_results=max_results_per_query)

    # 4. Merge & Deduplicate
    seen_urls: set[str] = set()
    unique_urls: list[str] = []

    for url in urls_primary + urls_secondary:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append(url)

    # Fallback search if zero results were found on the specific queries
    if not unique_urls:
        query_fallback = f"imobiliarias {city_clean} {country_clean}"
        logger.info(f"Attempting fallback query: '{query_fallback}'")
        urls_fallback = execute_ddg_search(query_fallback, max_results=max_results_per_query)
        for url in urls_fallback:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)

    logger.info(
        f"Discovery finished. "
        f"Total unique URLs after deduplication: {len(unique_urls)}"
    )

    # 5. Fail-Fast Policy on Empty Results
    if not unique_urls:
        raise NoResultsFoundError(
            f"No real estate websites found for location: '{city_clean}, {country_clean}' with query '{query_primary}'. "
            "Halting pipeline early to avoid empty downstream operations."
        )

    return unique_urls
