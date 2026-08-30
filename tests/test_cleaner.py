import pytest
from src.scraper.cleaner import clean_markdown_content


def test_clean_markdown_strips_images():
    raw_markdown = """
    # Imóveis à Venda
    ![Image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=)
    ![Photo](https://example.com/photo.jpg)
    Apartamento com 3 quartos à venda por R$ 800.000 no bairro Cambuí.
    """
    cleaned = clean_markdown_content(raw_markdown)
    assert "data:image" not in cleaned
    assert "https://example.com/photo.jpg" not in cleaned
    assert "R$ 800.000" in cleaned
    assert "Cambuí" in cleaned


def test_clean_markdown_removes_cookie_noise():
    raw_markdown = """
    Política de Privacidade e Termos de Uso.
    Utilizamos cookies para personalizar sua experiência.
    Casa à venda com 4 dormitórios e 2 suítes por R$ 1.500.000.
    Todos os direitos reservados.
    """
    cleaned = clean_markdown_content(raw_markdown)
    assert "Utilizamos cookies" not in cleaned
    assert "Política de Privacidade" not in cleaned
    assert "4 dormitórios" in cleaned


def test_clean_markdown_caps_length():
    repeated_line = "Apartamento à venda por R$ 500.000 com 2 quartos e 60 m².\n"
    raw_markdown = repeated_line * 500
    cleaned = clean_markdown_content(raw_markdown, max_length=1000)
    assert len(cleaned) <= 1000


def test_clean_markdown_empty_input():
    assert clean_markdown_content("") == ""
    assert clean_markdown_content("   ") == ""
