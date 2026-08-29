import asyncio
import logging
import re
from typing import Dict, List, Optional
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# Shared requests session for connection pooling and fast TCP reuse
_HTTP_SESSION: Optional[requests.Session] = None


def _get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        _HTTP_SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=2)
        _HTTP_SESSION.mount("https://", adapter)
        _HTTP_SESSION.mount("http://", adapter)
    return _HTTP_SESSION


def generate_paginated_urls(base_url: str, max_pages: int = 1) -> List[str]:
    """
    Generates a list of paginated URLs for real estate listing pages.
    
    :param base_url: The primary listing URL (Page 1).
    :param max_pages: Number of pages to generate (e.g., 1, 2, 3...).
    :return: List of URLs for pages 1 through max_pages.
    """
    if max_pages <= 1 or not base_url:
        return [base_url] if base_url else []

    urls = [base_url]
    for page_num in range(2, max_pages + 1):
        if "?" in base_url:
            paginated = f"{base_url}&pagina={page_num}"
        elif base_url.endswith(".html"):
            paginated = f"{base_url}?pagina={page_num}"
        else:
            clean_base = base_url.rstrip("/")
            paginated = f"{clean_base}/?pagina={page_num}"
        urls.append(paginated)

    return urls


async def _crawl_single_url_crawl4ai(url: str) -> str:
    """
    Crawls a single URL using Crawl4AI AsyncWebCrawler if available.
    """
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if result and result.markdown:
                return result.markdown
            elif result and result.html:
                return result.html
    except Exception:
        logger.debug(f"Headless browser not active for '{url}', using fast direct HTTP session.")
    return ""


def _fallback_fetch_http(url: str, timeout: int = 15) -> str:
    """
    High-speed HTTP text extractor using requests session with desktop Chrome headers.
    """
    try:
        session = _get_http_session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
            "Sec-Ch-Ua": '"Chromium";v="128", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
        }
        resp = session.get(url, headers=headers, timeout=timeout, verify=False)
        if resp.status_code == 200:
            html_content = resp.text
            text = re.sub(r"<script.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        else:
            logger.debug(f"HTTP fetch returned status {resp.status_code} for '{url}'")
    except Exception as exc:
        logger.debug(f"Direct HTTP fetch exception for '{url}': {exc}")
    return ""


async def crawl_url(url: str) -> str:
    """
    Crawls a single URL, prioritizing Crawl4AI and falling back to HTTP fetcher if needed.

    :param url: The webpage URL to crawl.
    :return: Raw markdown or text extracted from the page.
    """
    logger.info(f"Crawling URL: {url}")
    
    # Try Crawl4AI first
    content = await _crawl_single_url_crawl4ai(url)
    if content and len(content.strip()) > 100:
        return content

    # Fallback to direct HTTP fetch
    return _fallback_fetch_http(url)


async def crawl_urls(urls: List[str], concurrency_limit: int = 3) -> Dict[str, str]:
    """
    Crawls multiple URLs concurrently with a concurrency semaphore.

    :param urls: List of URLs to scrape.
    :param concurrency_limit: Maximum number of concurrent browser tabs/requests.
    :return: Dictionary mapping URL to raw scraped markdown/text content.
    """
    semaphore = asyncio.Semaphore(concurrency_limit)
    results: Dict[str, str] = {}

    async def _worker(target_url: str):
        async with semaphore:
            scraped_text = await crawl_url(target_url)
            if scraped_text:
                results[target_url] = scraped_text

    tasks = [_worker(u) for u in urls]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results


def crawl_urls_sync(urls: List[str], concurrency_limit: int = 3) -> Dict[str, str]:
    """
    Synchronous helper wrapper for crawl_urls.
    """
    return asyncio.run(crawl_urls(urls=urls, concurrency_limit=concurrency_limit))
