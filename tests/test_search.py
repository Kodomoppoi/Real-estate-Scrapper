import pytest
from src.search.ddg_engine import (
    _normalize_url,
    _format_property_terms,
    discover_real_estate_urls,
    InvalidLocationError,
)


def test_normalize_url():
    assert _normalize_url("https://example.com/imoveis/") == "https://example.com/imoveis"
    assert _normalize_url("  https://example.com/busca/?pagina=2  ") == "https://example.com/busca?pagina=2"
    assert _normalize_url("ftp://invalid.com") == ""
    assert _normalize_url("") == ""


def test_format_property_terms():
    prop, trans = _format_property_terms("casa", "venda")
    assert prop == "casas"
    assert trans == "a venda"

    prop_apt, trans_rent = _format_property_terms("apartamento", "aluguel")
    assert prop_apt == "apartamentos"
    assert trans_rent == "para alugar"


def test_discover_real_estate_urls_validation():
    with pytest.raises(InvalidLocationError):
        discover_real_estate_urls(country="", city="São Paulo")

    with pytest.raises(InvalidLocationError):
        discover_real_estate_urls(country="Brasil", city="")
