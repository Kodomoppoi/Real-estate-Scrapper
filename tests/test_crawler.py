import pytest
from src.scraper.crawler import generate_paginated_urls


def test_generate_paginated_urls_single_page():
    urls = generate_paginated_urls("https://example.com/imoveis", max_pages=1)
    assert urls == ["https://example.com/imoveis"]


def test_generate_paginated_urls_multi_page():
    urls = generate_paginated_urls("https://example.com/imoveis", max_pages=3)
    assert len(urls) == 3
    assert urls[0] == "https://example.com/imoveis"
    assert urls[1] == "https://example.com/imoveis/?pagina=2"
    assert urls[2] == "https://example.com/imoveis/?pagina=3"


def test_generate_paginated_urls_with_query():
    urls = generate_paginated_urls("https://example.com/busca?tipo=casa", max_pages=2)
    assert len(urls) == 2
    assert urls[1] == "https://example.com/busca?tipo=casa&pagina=2"
