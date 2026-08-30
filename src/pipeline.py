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
    LLMExtractionError,
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
        saved_file_path: Optional[str] = None,
        is_partial: bool = False
    ):
        self.country = country
        self.city = city
        self.discovered_candidates = discovered_candidates
        self.curated_sites = curated_sites
        self.crawled_urls = crawled_urls
        self.properties = properties
        self.dataframe = dataframe
        self.saved_file_path = saved_file_path
        self.is_partial = is_partial


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
    2. AI Curation: LLM selects top N deep URLs by index matching location and country language.
    3. Pagination Expansion: Generates Page 1, 2, 3... for the curated deep routes.
    4. Concurrent Crawling: Fetches listing pages.
    5. Token Cleaning: Strips noisy boilerplate.
    6. LLM Structured Extraction: Extracts property listings adapted to target country.
    7. Fail-Fast Validation: Aborts with NoPropertiesExtractedError if 0 properties are found.
    8. Aggregation & CSV Export.
    """
    logger.info(
        f"Starting Scraper Pipeline for '{city}, {country}' "
        f"[Type: {property_type or 'Todos'}, Action: {transaction_type or 'Venda'}, "
        f"AI Top Sites: {max_sites_to_curate}, Pages/Site: {max_pages_per_site}]"
    )

    # Step 1: Discover candidate websites from search engine (scaled dynamically)
    candidate_pool_size = max(max_sites_to_curate * 2, 20)
    candidate_urls = discover_real_estate_urls(
        country=country,
        city=city,
        property_type=property_type,
        transaction_type=transaction_type,
        max_results_per_query=candidate_pool_size
    )
    logger.info(f"Discovered {len(candidate_urls)} raw candidate URLs from search.")

    # Step 2: AI Curation (LLM picks top N deep listing URLs by index)
    curated_sites = curate_top_real_estate_sites(
        candidate_urls=candidate_urls,
        target_city=city,
        country=country,
        max_sites=max_sites_to_curate
    )
    logger.info(f"AI Curated {len(curated_sites)} primary real estate deep URLs to scrape.")

    # Step 3, 4 & 5: Progressive Portal-by-Portal Crawling with Early Abandonment
    all_properties: List[PropertyListing] = []
    crawled_urls: List[str] = []
    halt_pipeline_due_to_quota: bool = False

    for site_idx, site_url in enumerate(curated_sites, start=1):
        if halt_pipeline_due_to_quota:
            break

        logger.info(f"Processing Portal {site_idx}/{len(curated_sites)}: '{site_url}'")

        # 1. Test Page 1 of the portal first
        page1_data = await crawl_urls(urls=[site_url], concurrency_limit=concurrency_limit)
        raw_page1 = page1_data.get(site_url, "")
        cleaned_page1 = clean_markdown_content(raw_page1)

        if not cleaned_page1 or len(cleaned_page1.strip()) < 80:
            logger.info(f"[SKIP] Portal '{site_url}' returned empty or blocked content on Page 1. Aborting remaining pages for this portal.")
            continue

        crawled_urls.append(site_url)

        try:
            page1_properties = extract_properties_from_text(
                cleaned_text=cleaned_page1,
                target_city=city,
                country=country,
                source_url=site_url
            )
        except LLMExtractionError as exc:
            if all_properties:
                logger.warning(
                    f"[PARTIAL SUCCESS] AI quota limit reached on '{site_url}'. "
                    f"Preserving and delivering all {len(all_properties)} properties collected so far."
                )
                halt_pipeline_due_to_quota = True
                break
            else:
                logger.error(f"[ABORT] Critical AI error with 0 properties collected: {exc}. Halting pipeline immediately.")
                raise exc
        except Exception as exc:
            logger.warning(f"Unexpected error extracting listings from '{site_url}': {exc}. Skipping portal.")
            continue

        # If Page 1 returned 0 properties, immediately ABORT this portal and jump to the next one!
        if not page1_properties:
            logger.info(f"[SKIP] Portal '{site_url}' yielded 0 listings on Page 1. Aborting this site to save tokens and moving to next portal...")
            continue

        all_properties.extend(page1_properties)
        logger.info(f"[OK] Extracted {len(page1_properties)} listings from Page 1 of '{site_url}'.")

        # 2. Only if Page 1 succeeded and max_pages_per_site > 1, process subsequent pages
        if max_pages_per_site > 1:
            paginated_links = generate_paginated_urls(site_url, max_pages=max_pages_per_site)[1:]
            for page_num, next_page_url in enumerate(paginated_links, start=2):
                logger.info(f"Crawling Page {page_num}/{max_pages_per_site} of portal '{site_url}'...")
                next_page_data = await crawl_urls(urls=[next_page_url], concurrency_limit=concurrency_limit)
                raw_next = next_page_data.get(next_page_url, "")
                cleaned_next = clean_markdown_content(raw_next)

                if not cleaned_next or len(cleaned_next.strip()) < 80:
                    logger.info(f"Page {page_num} of '{site_url}' is empty. Stopping pagination for this portal.")
                    break

                crawled_urls.append(next_page_url)
                try:
                    next_properties = extract_properties_from_text(
                        cleaned_text=cleaned_next,
                        target_city=city,
                        country=country,
                        source_url=next_page_url
                    )
                    if not next_properties:
                        logger.info(f"Page {page_num} yielded 0 listings. Stopping pagination for '{site_url}'.")
                        break
                    all_properties.extend(next_properties)
                    logger.info(f"[OK] Extracted {len(next_properties)} listings from Page {page_num}.")
                except LLMExtractionError as exc:
                    if all_properties:
                        logger.warning(
                            f"[PARTIAL SUCCESS] AI quota limit reached on Page {page_num}. "
                            f"Preserving and delivering all {len(all_properties)} properties collected so far."
                        )
                        halt_pipeline_due_to_quota = True
                        break
                    else:
                        logger.error(f"[ABORT] Critical AI error on Page {page_num} with 0 properties collected: {exc}. Halting pipeline.")
                        raise exc
                except Exception as exc:
                    logger.warning(f"Error on Page {page_num} of '{site_url}': {exc}. Stopping pagination for this portal.")
                    break

    # Step 6: Fail-Fast Policy on zero extracted properties
    if not all_properties:
        raise NoPropertiesExtractedError(
            f"No property listings were extracted for '{city}, {country}'. "
            f"The visited real estate portals contained no matching listings for this location, blocked automated access, or the AI request quota was exceeded."
        )

    logger.info(f"Pipeline completed. Total properties extracted: {len(all_properties)}")

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
        crawled_urls=crawled_urls,
        properties=all_properties,
        dataframe=df,
        saved_file_path=saved_path,
        is_partial=halt_pipeline_due_to_quota
    )
