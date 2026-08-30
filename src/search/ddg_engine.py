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


def _is_portuguese_locale(country: str) -> bool:
    """Checks if target country is Portuguese-speaking."""
    country_lower = country.strip().lower()
    return any(c in country_lower for c in ["brasil", "brazil", "portugal", "angola", "moçambique", "mozambique"])


def _format_property_terms(prop: Optional[str], trans: Optional[str], is_pt: bool = True) -> Tuple[str, str]:
    """
    Normalizes and pluralizes property types and transaction terms for natural search engine queries,
    adapting dynamically to Portuguese or English based on the target country.
    """
    p_clean = prop.strip().lower() if prop else "all"
    t_clean = trans.strip().lower() if trans else "sale"

    if is_pt:
        p_map = {
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
            "sitio": "chácaras",
            "sítio": "chácaras",
            "fazenda": "fazendas",
            "cobertura": "coberturas",
            "coberturas": "coberturas",
            "studio": "studios",
            "kitnet": "studios",
            "comercial": "imoveis comerciais",
            "todos": "imoveis",
            "apartment": "apartamentos",
            "apartments": "apartamentos",
            "house": "casas",
            "houses": "casas",
            "land": "terrenos",
            "commercial": "imoveis comerciais",
            "penthouse": "coberturas",
            "farm / ranch": "chácaras",
            "all": "imoveis",
        }
        t_map = {
            "venda": "a venda",
            "comprar": "a venda",
            "aluguel": "para alugar",
            "locacao": "para alugar",
            "locação": "para alugar",
            "todos": "a venda",
            "sale": "a venda",
            "buy": "a venda",
            "rent": "para alugar",
            "lease": "para alugar",
            "all": "a venda",
        }
        return p_map.get(p_clean, p_clean), t_map.get(t_clean, "a venda")

    # English / International mapping
    p_map_en = {
        "apartment": "apartments",
        "apartments": "apartments",
        "apartamento": "apartments",
        "house": "houses",
        "houses": "houses",
        "casa": "houses",
        "land": "land",
        "land / lot": "land",
        "terreno": "land",
        "commercial": "commercial properties",
        "comercial": "commercial properties",
        "penthouse": "penthouses",
        "cobertura": "penthouses",
        "farm / ranch": "ranches and farms",
        "farm": "farms",
        "all": "homes",
        "todos": "homes",
    }
    t_map_en = {
        "sale": "for sale",
        "buy": "for sale",
        "venda": "for sale",
        "rent": "for rent",
        "lease": "for rent",
        "aluguel": "for rent",
        "all": "for sale",
        "todos": "for sale",
    }
    return p_map_en.get(p_clean, "homes"), t_map_en.get(t_clean, "for sale")


def _generate_fallback_portal_urls(city_clean: str, country_clean: str, prop_term: str, trans_term: str, is_pt: bool = True) -> List[str]:
    """Generates direct listing search URLs for the top portals if search engine is temporarily throttled."""
    slug_city = re.sub(r"[^a-zA-Z0-9]+", "-", city_clean.lower()).strip("-")

    if not is_pt:
        slug_action = "rent" if "rent" in trans_term else "for-sale"
        return [
            f"https://www.realtor.com/realestateandhomes-search/{slug_city}",
            f"https://www.zillow.com/{slug_city}/",
            f"https://www.redfin.com/city/{slug_city}",
            f"https://www.trulia.com/{country_clean.lower()}/{slug_city}/"
        ]

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
    """
    if not country or not country.strip():
        raise InvalidLocationError("The 'country' parameter cannot be empty.")
    if not city or not city.strip():
        raise InvalidLocationError("The 'city' parameter cannot be empty.")

    country_clean = country.strip()
    city_clean = re.sub(r"[,;]", " ", city).strip()
    city_clean = re.sub(r"\s+", " ", city_clean)
    
    is_pt = _is_portuguese_locale(country_clean)
    prop_term, trans_term = _format_property_terms(property_type, transaction_type, is_pt=is_pt)

    logger.info(
        f"Starting real estate discovery for: {city_clean}, {country_clean} "
        f"[Type: {prop_term}, Action: {trans_term}]"
    )

    if is_pt:
        query_primary = f"{prop_term} {trans_term} {city_clean}"
        query_secondary = f"imoveis {trans_term} {city_clean}"
        query_fallback = f"imobiliarias {city_clean}"
    else:
        query_primary = f"{prop_term} {trans_term} {city_clean} {country_clean}"
        query_secondary = f"real estate {trans_term} in {city_clean} {country_clean}"
        query_fallback = f"real estate agencies in {city_clean}"

    urls_primary = execute_ddg_search(query_primary, max_results=max_results_per_query)
    urls_secondary = execute_ddg_search(query_secondary, max_results=max_results_per_query)

    seen_urls: set[str] = set()
    unique_urls: List[str] = []

    for url in urls_primary + urls_secondary:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append(url)

    if not unique_urls:
        logger.info(f"Attempting fallback query: '{query_fallback}'")
        urls_fallback = execute_ddg_search(query_fallback, max_results=max_results_per_query)
        for url in urls_fallback:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)

    if not unique_urls:
        logger.info("Search engine returned 0 results. Activating smart direct portal fallback...")
        fallback_seeds = _generate_fallback_portal_urls(city_clean, country_clean, prop_term, trans_term, is_pt=is_pt)
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
