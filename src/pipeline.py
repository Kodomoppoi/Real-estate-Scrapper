import logging
from datetime import datetime
from typing import List, Optional
import pandas as pd

from config.settings import (
    DATA_PROCESSED_DIR,
    CRAWLER_CONCURRENCY_LIMIT,
    DEFAULT_MAX_PAGES_PER_SITE,
)
from src.search import discover_real_estate_urls
from src.scraper import crawl_urls, clean_markdown_content, generate_paginated_urls
from src.extractor import (
    extract_properties_from_text,
    curate_top_real_estate_sites,
    PropertyListing,
    NoPropertiesExtractedError,
)

logger = logging.getLogger(__name__)


class ScraperPipelineResult:
    """
    Encapsulates the final results and metadata of the end-to-end scraper pipeline.
    """
    def __init__(
        self,
        country: str,
        city: str,
        discovered_candidates: List[str],
        curated_sites: List[str],
        crawled_urls: List[str],
        properties: List[PropertyListing],
        dataframe: pd.DataFrame,
        saved_file_path: Optional[str] = None
    ):
        self.country = country
        self.city = city
        self.discovered_candidates = discovered_candidates
        self.curated_sites = curated_sites
        self.crawled_urls = crawled_urls
        self.properties = properties
        self.dataframe = dataframe
        self.saved_file_path = saved_file_path


async def run_pipeline_async(
    country: str,
    city: str,
    property_type: Optional[str] = None,
    transaction_type: Optional[str] = None,
    max_sites_to_curate: int = 2,
    max_pages_per_site: int = DEFAULT_MAX_PAGES_PER_SITE,
    save_to_csv: bool = True,
    concurrency_limit: int = CRAWLER_CONCURRENCY_LIMIT
) -> ScraperPipelineResult:
    """
    Executes the full automated Real Estate Scraping and Extraction pipeline:
    1. Search & Discovery: Gathers broad candidate websites from DuckDuckGo.
    2. AI Curation: LLM selects top N deep URLs by index (preserving full listing paths).
    3. Pagination Expansion: Generates Page 1, 2, 3... for the curated deep routes.
    4. Concurrent Crawling: Fetches listing pages.
    5. Token Cleaning: Strips noisy boilerplate.
    6. LLM Structured Extraction: Extracts property listings for the target city.
    7. Fail-Fast Validation: Aborts with NoPropertiesExtractedError if 0 properties are found.
    8. Aggregation & CSV Export.
    """
    logger.info(
        f"=== Starting Scraper Pipeline for '{city}, {country}' "
        f"[Type: {property_type or 'Todos'}, Action: {transaction_type or 'Venda'}, "
        f"AI Top Sites: {max_sites_to_curate}, Pages/Site: {max_pages_per_site}] ==="
    )

    # Step 1: Discover candidate websites from search engine
    candidate_urls = discover_real_estate_urls(
        country=country,
        city=city,
        property_type=property_type,
        transaction_type=transaction_type,
        max_results_per_query=6  # Broad candidate pool
    )
    logger.info(f"Discovered {len(candidate_urls)} raw candidate URLs from search.")

    # Step 2: AI Curation (LLM picks top N deep listing URLs by index)
    curated_sites = curate_top_real_estate_sites(
        candidate_urls=candidate_urls,
        target_city=city,
        max_sites=max_sites_to_curate
    )
    logger.info(f"AI Curated {len(curated_sites)} primary real estate deep URLs to scrape.")

    # Step 3: Expand URLs with pagination for curated deep sites
    target_urls: List[str] = []
    for url in curated_sites:
        paginated_links = generate_paginated_urls(url, max_pages=max_pages_per_site)
        target_urls.extend(paginated_links)

    logger.info(f"Total target pages to crawl: {len(target_urls)}")

    # Step 4: Crawl all expanded pages concurrently
    scraped_data = await crawl_urls(urls=target_urls, concurrency_limit=concurrency_limit)
    logger.info(f"Successfully scraped content from {len(scraped_data)}/{len(target_urls)} pages.")

    # Step 5: Clean and Extract with LLM for each page
    all_properties: List[PropertyListing] = []

    for page_url, raw_content in scraped_data.items():
        cleaned_text = clean_markdown_content(raw_content)
        if not cleaned_text or len(cleaned_text.strip()) < 80:
            continue

        try:
            extracted = extract_properties_from_text(
                cleaned_text=cleaned_text,
                target_city=city,
                source_url=page_url
            )
            all_properties.extend(extracted)
        except Exception as exc:
            logger.warning(f"Skipping extraction for '{page_url}' due to error: {exc}")

    # Step 6: Fail-Fast Policy on zero extracted properties
    if not all_properties:
        raise NoPropertiesExtractedError(
            f"Nenhum imóvel foi extraído para a localização '{city}, {country}'. "
            f"As páginas visitadas não continham listagens compatíveis ou o conteúdo foi bloqueado."
        )

    logger.info(f"=== Pipeline completed. Total properties extracted: {len(all_properties)} ===")

    # Step 7: Convert to Pandas DataFrame and Deduplicate
    records = [p.model_dump() for p in all_properties]
    df = pd.DataFrame(records)

    if not df.empty and "title" in df.columns and "price" in df.columns:
        initial_len = len(df)
        df = df.drop_duplicates(subset=["title", "price", "neighborhood"], keep="first")
        if len(df) < initial_len:
            logger.info(f"Removed {initial_len - len(df)} duplicate listings across pages.")

    # Step 8: Export to CSV
    saved_path = None
    if save_to_csv and not df.empty:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_city_name = city.lower().replace(" ", "_")
        csv_filename = f"properties_{clean_city_name}_{timestamp}.csv"
        target_path = DATA_PROCESSED_DIR / csv_filename
        df.to_csv(target_path, index=False, encoding="utf-8-sig")
        saved_path = str(target_path)
        logger.info(f"Saved processed listings to: {saved_path}")

    return ScraperPipelineResult(
        country=country,
        city=city,
        discovered_candidates=candidate_urls,
        curated_sites=curated_sites,
        crawled_urls=target_urls,
        properties=all_properties,
        dataframe=df,
        saved_file_path=saved_path
    )
