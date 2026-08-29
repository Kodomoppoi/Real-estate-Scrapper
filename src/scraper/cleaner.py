import re
import logging
from typing import List, Pattern
from config.settings import CLEANER_MAX_CHARS

logger = logging.getLogger(__name__)

# Keywords associated with real estate property listings across languages
REAL_ESTATE_KEYWORDS: List[str] = [
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
NOISE_PATTERNS: List[str] = [
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

# Precompiled regular expressions for maximum throughput
RE_IMG_BASE64: Pattern = re.compile(r"!\[.*?\]\(data:image\/.*?\)")
RE_IMG_HTTP: Pattern = re.compile(r"!\[.*?\]\(http.*?\)")
RE_LINK_TEXT: Pattern = re.compile(r"\[(.*?)\]\(http.*?\)")
RE_NOISE: List[Pattern] = [re.compile(p) for p in NOISE_PATTERNS]
RE_KEYWORD: Pattern = re.compile("|".join(REAL_ESTATE_KEYWORDS), re.IGNORECASE)
RE_EXCESS_NEWLINES: Pattern = re.compile(r"\n{3,}")
RE_EXCESS_SPACES: Pattern = re.compile(r"[ \t]{2,}")


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

    # 1. Strip images and simplify markdown links to text
    text = RE_IMG_BASE64.sub("", text)
    text = RE_IMG_HTTP.sub("", text)
    text = RE_LINK_TEXT.sub(r"\1", text)

    # 2. Strip common cookie/legal boilerplate
    for pattern in RE_NOISE:
        text = pattern.sub("", text)

    # 3. Filter lines by real estate relevance and deduplicate consecutive identical lines
    lines = text.splitlines()
    filtered_lines: List[str] = []
    seen_previous_line = ""

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == seen_previous_line:
            continue

        # Keep lines that match property features, headers, tables, or descriptive phrases
        if stripped.startswith(("#", "-", "*", "|")) or RE_KEYWORD.search(stripped):
            filtered_lines.append(stripped)
            seen_previous_line = stripped
        elif len(stripped) > 25 and any(char.isdigit() for char in stripped):
            # Keep descriptive addresses, codes, or specs with digits
            filtered_lines.append(stripped)
            seen_previous_line = stripped

    cleaned_text = "\n".join(filtered_lines)

    # 4. Collapse whitespace
    cleaned_text = RE_EXCESS_NEWLINES.sub("\n\n", cleaned_text)
    cleaned_text = RE_EXCESS_SPACES.sub(" ", cleaned_text).strip()

    # 5. Cap text length to conserve token budget
    if len(cleaned_text) > max_length:
        logger.info(f"Condensing text from {len(cleaned_text)} to {max_length} chars for token efficiency.")
        cleaned_text = cleaned_text[:max_length]

    return cleaned_text
