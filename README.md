# Real Estate Scraper & AI Extractor

An intelligent, token-efficient pipeline designed to automatically discover real estate websites, crawl listing pages, and extract structured property data using LLM Structured Outputs.

---

## 🏗️ Architecture & Non-Obvious Design Decisions

```text
Location & Filters (e.g. Ipanema, Rio de Janeiro / Brasil)
       │
       ▼
1. Direct Listing Discovery (DuckDuckGo Engine - Scaled Candidates)
       │
       ▼
2. AI Pre-Curation & Index Matching (Preserves exact deep routes & filters noise)
       │
       ▼
3. Pagination Expansion (Generates multi-page routes up to 10 pages)
       │
       ▼
4. Dual-Engine Crawler (Crawl4AI / Playwright + Stealth HTTP Fallback)
       │
       ▼
5. Token Condensation Cleaner (~75% DOM & noise reduction)
       │
       ▼
6. Country-Aware Structured Extraction (Suites, Amenities, Highlights, Financing)
       │
       ▼
7. Pandas Consolidation, Deduplication & CSV Export (UTF-8-SIG)
```

### 1. Direct Deep-Query Discovery vs. Homepage Crawling
* **Why**: Real estate homepages are filled with dynamic search forms, auth modals, and institutional banners, but rarely contain listings directly.
* **How**: Rather than automating search form inputs on hundreds of distinct CMS platforms, the discovery engine uses natural-language pluralized queries (e.g., `apartamentos a venda em Ipanema Rio de Janeiro`). The search engine performs the routing work for free, returning deep listing URLs (e.g., `/venda/rj/rio-de-janeiro/zona-sul/ipanema/apartamento`).

### 2. Index-Matched AI Pre-Curation
* **Why**: Asking an LLM to re-type or output raw URLs frequently leads to hallucinated links or truncated root domains (e.g., returning `zapimoveis.com.br/` instead of the full filtered search route).
* **How**: Candidate URLs are numbered and passed in batch to the LLM. The model selects the best candidate portals by integer indexes (`[1, 3]`), allowing the system to retrieve the exact full-path listing URLs with zero corruption.

### 3. Country-Aware Language Localization
* **Why**: A global scraper should parse properties from any country without mixing languages.
* **How**: The extraction prompt dynamically detects the target country and enforces output descriptions, amenities, and highlights in that country's official language (Portuguese for Brazil/Portugal, English for USA/UK, Spanish for Spain/Latam, etc.).

### 4. Enriched Deep Extraction from Headlines
* **Why**: Property cards in listing feeds pack key decision criteria into headline text (e.g. *"Apartamento reformado com 3 quartos (2 suítes), varanda gourmet, piscina, aceita financiamento"*).
* **How**: The Pydantic schema extracts structured sub-attributes:
  - `suites`: Count of master bedrooms / suites.
  - `amenities`: Infrastructure and leisure tags (*Pool, Barbecue, Balcony, Gated Community, Gym, Pet Friendly*).
  - `financing_accepted`: Explicit financing / mortgage eligibility.
  - `highlights`: Summary of key differentiators extracted from the headline.

### 5. High-Density Token Condensation (~75% Noise Reduction)
* **Why**: A scraped webpage easily exceeds 100,000+ characters of SVGs, cookie policies, navigation bars, and footer links across 500 cities. Sending raw HTML/DOM to an LLM exhausts TPM limits and increases latency.
* **How**: The `cleaner.py` module strips base64 media, boilerplates, and filters text to retain only lines containing property attributes (`R$`, `m²`, `quartos`, `bairro`, `endereço`), compressing the payload to ~15,000 characters without losing listing details.

### 6. Free-Tier Rate Limiting & Cooldown Backoff
* **Why**: The free tier of Gemini Flash enforces a 15 RPM (Requests Per Minute) cap and strict burst limits. Bursting multiple pages concurrently causes immediate `429 Too Many Requests` errors.
* **How**: The extractor paces calls with a configurable safety delay (4s) and applies progressive exponential backoff (waiting 8s, 14s, 20s...) when a 429 status is encountered, allowing large batches to complete autonomously.

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
Create a `.env` file in the project root (or configure it directly inside the Web UI):
```ini
GEMINI_API_KEY="your_google_ai_studio_api_key"
LLM_MODEL=gemini-3.6-flash
```

*(Note: The pipeline also supports OpenAI models like `gpt-4o-mini` or OpenRouter by setting `OPENAI_API_KEY` and `LLM_MODEL` in the Web UI).*

### 3. Launch the Web Dashboard
```powershell
streamlit run app.py
```

---

## 🖥️ Web Dashboard Features

- **Real-Time Terminal Activity**: Live streaming terminal box embedded directly inside the browser showing search, crawling, and AI steps.
- **In-App API Key Manager**: Test and save Gemini or OpenAI API keys directly from the sidebar.
- **KPI Metrics Cards**: Total listings, estimated average market price, median area ($m^2$), and top neighborhood.
- **Interactive Listings Table**: Client-side keyword search, neighborhood filters, bedroom filters, and direct links to original ads.
- **Market Visual Analytics**: Distribution histograms by neighborhood and bedroom counts, alongside $m^2$ vs Price scatter plots.
- **Extra Details Tab**: Amenity frequency rankings, financing status breakdown, and Price-per-$m^2$ calculation rankings.
- **One-Click Export**: Export consolidated datasets to CSV (Excel compatible with `utf-8-sig`) and JSON.
