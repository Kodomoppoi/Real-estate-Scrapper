# Real Estate Scraper & AI Extractor

[![GitHub Release](https://img.shields.io/badge/Release-v1.0.0-blue.svg)](https://github.com/Kodomoppoi/Real-estate-Scrapper/releases)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

An intelligent, token-efficient pipeline designed to automatically discover real estate websites, crawl listing pages, and extract structured property data using LLM Structured Outputs.
---
VIDEO SHOWCASE : https://youtu.be/xcjRcRTZt-I?si=thM-5ZTkQCM7sZmI

---


![Dashboard Overview](docs/screenshots/dashboard_overview.png)
*Interactive Real Estate Explorer with KPI metrics, AI curated portals, and property listing tables.*

<p align="center" width="100%">
<video src="https://youtu.be/xcjRcRTZt-I?si=thM-5ZTkQCM7sZmI" width="80%" controls></video>
</p>

---

> ⚠️ **Important Note on Crawl Settings, Model Selection & Rate Limits (TPM):**
> 
> 1. **Exponential Crawl Scaling**: The total number of crawled pages, AI token expenditure, and overall execution time increase **exponentially** with the **Crawl Settings** (`AI Curated Sites` × `Pages per Site`).
>    * **For Testing**: It is strongly recommended to set **1 Curated Site** and **1 Page per Site (`1 / 1`)** to verify location results quickly and conserve API quota.
>    * **For Full Scrapes**: Increase to higher limits (e.g., 2–5 sites, 2–3 pages) once you confirm portal accessibility.
> 
> 2. **AI Provider Capacity & Extraction Yield (TPM Limits)**:
>    * **Google Gemini (`gemini-3.6-flash`) [Recommended for Maximum Volume]**: Features a 4,000,000 TPM limit and 1M context window. It effortlessly extracts **20 to 25 complete listings per page** in seconds.
>    * **Groq Cloud (Free Tier)**: Provides ultra-fast LPU inference, but large 70B/120B models (e.g. `openai/gpt-oss-120b`) have a tight ~6,000 TPM cap that can rate-limit full-page extraction down to only 1–2 listings per request. **For Groq, use high-throughput models** like `qwen/qwen3.6-27b`, `groq/compound-mini`, or `openai/gpt-oss-20b` (20,000+ TPM).

---

## 🏗️ Architecture

### Why AI?
Traditional web scrapers rely on brittle CSS/XPath selectors that constantly break whenever real estate portals change layouts, obfuscate class names, or render dynamic JavaScript feeds. 

By leveraging an **AI semantic extraction engine** with Pydantic structured outputs, this pipeline extracts clean, structured property data across any portal worldwide in any language without writing or maintaining site-specific scrapers.

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
3. Dual-Engine Crawler with Early Site Abandonment (Validates Page 1 first)
       │
       ▼
4. DOM Token Condensation (~75% Noise Reduction)
       │
       ▼
5. Country-Aware Structured Extraction (Suites, Amenities, Highlights, Financing)
       │
       ▼
6. Fail-Fast Resiliency, Pandas Deduplication & CSV/JSON Export
```

---

### Problems Solved in Pipeline Workflow:

#### 1. Search & Deep-Query Discovery
* **Problem Solved**: Real estate homepages are landing pages with complex search forms, while hardcoding portal URLs breaks across cities. The discovery engine performs targeted natural-language queries (e.g., `apartamentos a venda em Ipanema Rio de Janeiro`), retrieving live deep listing search URLs dynamically without form automation.

#### 2. Index-Matched AI Curation
* **Problem Solved**: Asking an LLM to rewrite or generate URLs causes link hallucinations or truncates deep paths to root domains (e.g. returning `zapimoveis.com.br/`). By numbering candidate URLs and having the LLM select 1-based integer indexes (`[1, 2]`), exact deep paths are preserved with 100% fidelity.

#### 3. Progressive Dual-Engine Crawling & Early Site Abandonment
* **Problem Solved**: Crawling multi-page routes on dead or anti-bot blocked portals wastes network time and AI tokens. Page 1 is validated first; if 0 listings are found or access is blocked, all remaining pages for that site are aborted immediately.

#### 4. DOM Token Condensation (~75% Noise Reduction)
* **Problem Solved**: Raw webpage HTML contains 80,000+ characters of SVGs, cookie banners, navigation menus, and ads. The regex cleaner strips noise and filters text to retain only property-relevant signals (`R$`, `m²`, `quartos`, `amenities`), fitting within fast LLM token windows.

#### 5. Country-Aware Structured Extraction
* **Problem Solved**: Property listings are unstructured and written in diverse regional formats. The Pydantic schema extracts normalized attributes (`price`, `area_m2`, `bedrooms`, `suites`, `amenities`, `financing_accepted`) localized to the target country's official language.

#### 6. Fail-Fast Resiliency & Multi-Format Export
* **Problem Solved**: Rate limits and quota exhaustion previously led to long wait loops. The engine enforces immediate fail-fast handling on critical errors and compiles extracted records into deduplicated Pandas DataFrames for instant CSV (`utf-8-sig`) and JSON export.

---

## 🚀 Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/Kodomoppoi/Real-estate-Scrapper.git
cd Real-estate-Scrapper

# 2. Run the application
streamlit run app.py
```

---

## ⚙️ Configuration & API Keys

Configure your API key directly in the Web Dashboard sidebar or create a `.env` file in the project root:

```ini
# Google Gemini (Recommended - Free Tier available)
GEMINI_API_KEY=AIzaSy...
LLM_MODEL=gemini-3.6-flash

# Or OpenAI
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

---

## 🖥️ Web Dashboard Features

- **Real-Time Terminal Activity**: Live streaming terminal box embedded directly inside the browser showing search, crawling, and AI steps.
- **In-App API Key Manager**: Test and save Gemini, OpenAI, Groq, or OpenRouter API keys directly from the sidebar.
- **KPI Metrics Cards**: Total listings, estimated average market price, median area ($m^2$), and top neighborhood.
- **Interactive Listings Table**: Client-side keyword search, neighborhood filters, bedroom filters, price range filters, and direct links to original ads.
- **Extra Details Tab**: Amenity frequency rankings, financing status breakdown, and Price-per-$m^2$ calculation rankings.
- **One-Click Export**: Export consolidated datasets to CSV (Excel compatible with `utf-8-sig`) and JSON.

---

## 🧪 Automated Testing

Run the automated test suite with pytest:

```powershell
pytest tests/
```
