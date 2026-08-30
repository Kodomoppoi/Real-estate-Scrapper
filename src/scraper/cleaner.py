import re
import logging
from typing import List, Pattern, Optional
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
    r"garagens",
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
    r"fazenda",
    r"sítio",
    r"loft",
    r"flat",
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
    r"(?i)compre seu carro.*",
    r"(?i)links [uú]teis:?.*",
    r"(?i)buscas populares:?.*",
    r"(?i)im[oó]veis em cidades vizinhas:?.*",
]

# Precompiled regular expressions for maximum throughput
RE_IMG_BASE64: Pattern = re.compile(r"!\[.*?\]\(data:image\/.*?\)")
RE_IMG_HTTP: Pattern = re.compile(r"!\[.*?\]\(http.*?\)")
RE_LINK_TEXT: Pattern = re.compile(r"\[(.*?)\]\((http.*?)\)")
RE_NOISE: List[Pattern] = [re.compile(p) for p in NOISE_PATTERNS]
RE_KEYWORD: Pattern = re.compile("|".join(REAL_ESTATE_KEYWORDS), re.IGNORECASE)
RE_PRICE: Pattern = re.compile(r"R\$\s*[\d\.\,]+", re.IGNORECASE)
RE_METRICS: Pattern = re.compile(r"\b(?:\d+\s*m[²2]|\d+\s*(?:quartos?|dormit[oó]rios?|su[ií]tes?|banheiros?|vagas?|garagens?))\b", re.IGNORECASE)
RE_PROPERTY_HEADER: Pattern = re.compile(r"^(?:#+\s*)?(?:apartamento|casa|cobertura|terreno|sobrado|studio|kitnet|ch[aá]cara|loft|flat|fazenda|s[ií]tio|im[oó]vel)\b", re.IGNORECASE)
RE_EXCESS_NEWLINES: Pattern = re.compile(r"\n{3,}")
RE_EXCESS_SPACES: Pattern = re.compile(r"[ \t]{2,}")


def segment_and_format_listing_cards(cleaned_text: str) -> Optional[str]:
    """
    Identifies discrete property cards in the webpage text using anchor-based boundary detection.
    Groups prices, metrics, locations, and descriptions per listing, discarding surrounding noise.
    
    :param cleaned_text: Pre-stripped markdown text.
    :return: Formatted string with indexed listing cards, or None if discrete segmentation is not applicable.
    """
    lines = [l.strip() for l in cleaned_text.splitlines() if l.strip()]
    if not lines:
        return None

    cards: List[List[str]] = []
    current_card: List[str] = []

    for line in lines:
        is_header_or_type = bool(RE_PROPERTY_HEADER.search(line))
        has_price = bool(RE_PRICE.search(line))
        has_metrics = bool(RE_METRICS.search(line))

        # Check if this line marks the start of a NEW property listing
        # Triggered when encountering a new property type header AND the current card already contains a price or metrics
        current_has_price = any(RE_PRICE.search(c) for c in current_card)
        current_has_metrics = any(RE_METRICS.search(c) for c in current_card)

        if is_header_or_type and current_card and (current_has_price or current_has_metrics):
            cards.append(current_card)
            current_card = [line]
        elif current_card or is_header_or_type or has_price or has_metrics:
            current_card.append(line)

    if current_card and (any(RE_PRICE.search(c) for c in current_card) or any(RE_METRICS.search(c) for c in current_card)):
        cards.append(current_card)

    # Validate that we found at least 2 distinct property cards
    if len(cards) < 2:
        return None

    formatted_blocks: List[str] = []
    for idx, card_lines in enumerate(cards, start=1):
        card_text = "\n".join(card_lines)
        formatted_blocks.append(f"=== [IMÓVEL {idx}] ===\n{card_text}")

    logger.info(f"Anchor-Based Segmenter successfully isolated {len(cards)} discrete property cards.")
    return "\n\n".join(formatted_blocks)


def clean_markdown_content(raw_markdown: str, max_length: int = CLEANER_MAX_CHARS) -> str:
    """
    Cleans and optimizes scraped markdown text to minimize token consumption:
    - Strips base64 image strings, image URLs, and repetitive boilerplate.
    - Applies Anchor-Based Card Segmentation to isolate discrete listing blocks.
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

    # 1. Strip images and simplify markdown links to readable text with URL
    text = RE_IMG_BASE64.sub("", text)
    text = RE_IMG_HTTP.sub("", text)
    text = RE_LINK_TEXT.sub(r"\1 (\2)", text)

    # 2. Strip common cookie/legal/noise boilerplate
    for pattern in RE_NOISE:
        text = pattern.sub("", text)

    # 3. Attempt Anchor-Based Card Segmentation first
    segmented_cards = segment_and_format_listing_cards(text)
    if segmented_cards:
        final_text = segmented_cards
    else:
        # Fallback: Filter lines by real estate relevance and deduplicate consecutive lines
        lines = text.splitlines()
        filtered_lines: List[str] = []
        seen_previous_line = ""

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped == seen_previous_line:
                continue

            if stripped.startswith(("#", "-", "*", "|")) or RE_KEYWORD.search(stripped):
                filtered_lines.append(stripped)
                seen_previous_line = stripped
            elif len(stripped) > 25 and any(char.isdigit() for char in stripped):
                filtered_lines.append(stripped)
                seen_previous_line = stripped

        final_text = "\n".join(filtered_lines)

    # 4. Collapse whitespace
    final_text = RE_EXCESS_NEWLINES.sub("\n\n", final_text)
    final_text = RE_EXCESS_SPACES.sub(" ", final_text).strip()

    # 5. Cap text length to conserve token budget
    if len(final_text) > max_length:
        logger.info(f"Condensing text from {len(final_text)} to {max_length} chars for token efficiency.")
        final_text = final_text[:max_length]

    return final_text
