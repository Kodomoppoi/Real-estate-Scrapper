# Local Real Estate Scraper & AI Extractor

An intelligent, token-efficient pipeline designed to automatically discover real estate websites, crawl listing pages, and extract structured property data using LLM Structured Outputs.

---

## 🏗️ Architecture & Non-Obvious Design Decisions

```text
Location & Filters
       │
       ▼
1. Direct Listing Discovery (DuckDuckGo Engine)
       │
       ▼
2. AI Pre-Curation & Triage (Filters noise & picks Top N portals)
       │
       ▼
3. Pagination Expansion (Generates multi-page routes)
       │
       ▼
4. Dual-Engine Crawler (Crawl4AI + Stealth HTTP Fallback)
       │
       ▼
5. Token Condensation Cleaner (Filters ~75% DOM noise)
       │
       ▼
6. LLM Structured Extraction (Pydantic Schema + 15 RPM Rate Limiting)
       │
       ▼
7. Pandas Consolidation & Deduplication (CSV UTF-8-SIG)
```

### 1. Direct Deep-Query Discovery vs. Homepage Crawling
* **Why**: Real estate homepages are filled with dynamic search forms, auth modals, and institutional banners, but rarely contain listings directly.
* **How**: Rather than trying to automate search inputs on diverse CMS platforms, the discovery engine uses natural-language pluralized queries (e.g., `casas a venda em Jardim Botânico DF`). The search engine does the routing work for free, returning deep listing URLs (e.g., `/venda/df/brasilia/jardim-botanico/casa`).

### 2. AI Pre-Curation & Link Triage
* **Why**: Search engines inevitably return mixed results: real estate portals, but also broker Instagram profiles, Facebook groups, and general news blogs.
* **How**: Before dispatching the crawler, candidate URLs are sent in a single batch to the LLM. The model filters out non-listing domains (social media, news, forums) and selects only the Top N most reputable, high-density listing platforms.

### 3. Token Condensation Cleaner (~75% Noise Reduction)
* **Why**: A scraped webpage easily reaches 100,000+ characters of SVGs, cookie policies, navigation bars, and footer links across 500 cities. Sending this raw payload to an LLM exhausts TPM limits and increases latency.
* **How**: The `cleaner.py` module removes image data, boilerplate, and filters text to retain only lines containing property attributes (`R$`, `m²`, `quartos`, `bairro`, `endereço`), compressing the payload to ~15,000 characters without losing listing details.

### 4. Gemini Free-Tier Rate Limiting & Cooldown Backoff
* **Why**: The free tier of Gemini Flash enforces a 15 RPM (Requests Per Minute) cap and strict burst limits. Bursting multiple pages concurrently causes immediate `429 Too Many Requests` errors.
* **How**: The extractor paces calls with a configurable safety delay (4s) and applies progressive exponential backoff (waiting 8s, 14s, 20s...) when a 429 status is encountered, allowing large batches to complete autonomously.

### 5. Resilient Dual-Engine Crawler
* **Why**: Heavy JavaScript SPAs (React/Vue) require headless browser rendering, while simpler sites block headless bots with 403 Forbidden.
* **How**: The crawler attempts execution via `Crawl4AI` (Playwright), and if browser binaries are missing or blocked, immediately falls back to stealth HTTP requests with desktop Chrome headers.

---

## 🚀 Quick Start

### 1. Environment Setup
```powershell
# Create and activate local virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements.txt
```

### 2. Configure API Key
Create a `.env` file in the project root:
```ini
GEMINI_API_KEY="your_google_ai_studio_api_key"
LLM_MODEL=gemini-3.6-flash
```

### 3. Run the Interactive CLI
```powershell
python test.py
```
*(Provides interactive ASCII selection for Country, City, Property Type, Transaction Type, AI Curated Sites, and Pages per site).*

---

## 📦 Output Format

Extracted property listings are automatically deduplicated and exported to `data/processed/properties_{city}_{timestamp}.csv` with `utf-8-sig` encoding (fully compatible with Excel and Pandas).
