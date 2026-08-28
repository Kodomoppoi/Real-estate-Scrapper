import re
import logging
from config.settings import CLEANER_MAX_CHARS

logger = logging.getLogger(__name__)

# Keywords associated with real estate property listings
REAL_ESTATE_KEYWORDS = [
    r"r\$",
    r"preço",
    r"valor",
    r"venda",
    r"aluguel",
    r"locação",
    r"quartos?",
    r"dormit[oó]rios?",
    r"su[ií]tes?",
    r"banheiros?",
    r"vagas?",
    r"garagem",
    r"m[²2]",
    r"área",
    r"condom[ií]nio",
    r"iptu",
    r"bairro",
    r"endereço",
    r"apartamento",
    r"casa",
    r"terreno",
    r"sobrado",
    r"cobertura",
    r"kitnet",
    r"studio",
    r"chácara",
    r"price",
    r"rent",
    r"sale",
    r"bedrooms?",
    r"bathrooms?",
    r"sqft",
]

# Patterns representing non-relevant noisy elements
NOISE_PATTERNS = [
    r"(?i)pol[ií]tica de privacidade.*",
    r"(?i)termos de uso.*",
    r"(?i)todos os direitos reservados.*",
    r"(?i)utilizamos cookies.*",
    r"(?i)aceitar todos os cookies.*",
    r"(?i)powered by.*",
    r"(?i)copyright \d{4}.*",
    r"(?i)fale com o corretor.*",
    r"(?i)simular financiamento.*",
    r"(?i)envie uma proposta.*",
]


def clean_markdown_content(raw_markdown: str, max_length: int = CLEANER_MAX_CHARS) -> str:
    """
    Cleans and optimizes scraped markdown text to minimize token consumption:
    - Strips base64 image strings, image URLs, and repetitive boilerplate.
    - Preserves high-density property listing sections (prices, bedrooms, areas, neighborhoods).
    - Removes duplicate consecutive lines and shrinks excessive blank lines.
    - Limits total characters to fit within Free-Tier token budgets.

    :param raw_markdown: Raw text/markdown produced by the crawler.
    :param max_length: Maximum allowed character length for the output text.
    :return: Compact, token-efficient text ready for LLM extraction.
    """
    if not raw_markdown or not raw_markdown.strip():
        return ""

    text = raw_markdown

    # 1. Remove base64 image blobs and markdown image tags
    text = re.sub(r"!\[.*?\]\(data:image\/.*?\)", "", text)
    text = re.sub(r"!\[.*?\]\(http.*?\)", "", text)
    text = re.sub(r"\[.*?\]\(http.*?\)", lambda m: m.group(0).split("](")[0].lstrip("["), text)

    # 2. Remove common noise boilerplate
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text)

    # 3. Filter lines by real estate relevance and deduplicate consecutive identical lines
    lines = text.splitlines()
    filtered_lines: list[str] = []
    seen_previous_line = ""

    keyword_regex = re.compile("|".join(REAL_ESTATE_KEYWORDS), re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == seen_previous_line:
            continue
        
        # Keep lines that match property features, headers, tables, or descriptive phrases
        if stripped.startswith(("#", "-", "*", "|")) or keyword_regex.search(stripped):
            filtered_lines.append(stripped)
            seen_previous_line = stripped
        elif len(stripped) > 25 and any(char.isdigit() for char in stripped):
            # Keep descriptive addresses, codes, or specs with digits
            filtered_lines.append(stripped)
            seen_previous_line = stripped

    cleaned_text = "\n".join(filtered_lines)

    # 4. Collapse whitespace
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"[ \t]{2,}", " ", cleaned_text).strip()

    # 5. Cap text length to conserve token budget
    if len(cleaned_text) > max_length:
        logger.info(f"Condensing text from {len(cleaned_text)} to {max_length} chars for token efficiency.")
        cleaned_text = cleaned_text[:max_length]

    return cleaned_text
