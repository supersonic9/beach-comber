# Beach Comber — Portugal Property Price Tracker

## Overview

Track asking prices on Casa Sapo (casa.sapo.pt) across 4 Portuguese municipalities and all property types. Runs on a schedule via GitHub Actions, stores historical snapshots in Supabase PostgreSQL, and exposes data via a filterable Streamlit dashboard.

**Why Casa Sapo over Idealista:** server-rendered HTML, no DataDome anti-bot protection, existing working open-source scrapers, largest listing volume in Portugal.

---

## Architecture

```
GitHub Actions (cron schedule)
        │
        ▼
  Python scraper
        │
        ▼
  Supabase (PostgreSQL)   ◄──── Streamlit Cloud dashboard
```

No local infrastructure required after initial setup.

---

## Target Data

**4 search areas:**
- Póvoa de Varzim
- Vila do Conde
- Matosinhos
- Vila Nova de Gaia

**~10 property types:**
- apartamentos, moradias, terrenos, lojas, escritorios, predios, armazens, quintas-e-herdades, garagens, luxo

**Total combinations:** ~40 search runs per scrape cycle

**Casa Sapo URL pattern:**
```
https://casa.sapo.pt/comprar-{type}/{area-slug}/?pn={page}
```

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Language | Python 3.11+ | All existing scrapers use it |
| Scraping | `requests` + `BeautifulSoup4` | JSON-LD in HTML; avoids Selenium |
| Storage | Supabase PostgreSQL | Persistent, cloud-accessible, free tier |
| DB client | `psycopg2-binary` | Standard Postgres Python driver |
| Dashboard | Streamlit + Plotly | Python-native, interactive, Streamlit Cloud deploy |
| Scheduling | GitHub Actions | Cron trigger, easy frequency change, secrets management |

---

## Project Structure

```
beach-comber/
├── .github/
│   └── workflows/
│       └── scrape.yml       # GHA cron job
├── scraper/
│   ├── __init__.py
│   ├── config.py            # AREAS, PROPERTY_TYPES, env-configurable delays
│   ├── fetcher.py           # HTTP session, rate limiting, retry
│   ├── parser.py            # JSON-LD + BeautifulSoup extraction
│   └── db.py                # Postgres upsert operations
├── dashboard/
│   └── app.py               # Streamlit dashboard
├── schema.sql               # Run once in Supabase SQL editor
├── main.py                  # Entry point — loops all combinations
├── requirements.txt
├── .env.example             # DATABASE_URL=postgresql://...
└── .gitignore
```

---

## Database Schema

```sql
CREATE TABLE listings (
    id              TEXT PRIMARY KEY,
    property_type   TEXT NOT NULL,
    search_area     TEXT NOT NULL,
    location        TEXT,
    bedrooms        TEXT,
    price           INTEGER,
    price_per_sqm   REAL,
    size_sqm        REAL,
    condition       TEXT,
    url             TEXT,
    first_seen      DATE,
    last_seen       DATE,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE price_snapshots (
    id          SERIAL PRIMARY KEY,
    listing_id  TEXT NOT NULL REFERENCES listings(id),
    scraped_at  DATE NOT NULL,
    price       INTEGER,
    UNIQUE (listing_id, scraped_at)         -- idempotent: safe to re-run same day
);

CREATE TABLE scrape_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    total_listings  INTEGER,
    new_listings    INTEGER,
    price_changes   INTEGER,
    errors          INTEGER DEFAULT 0
);

CREATE INDEX ON listings(property_type);
CREATE INDEX ON listings(search_area);
CREATE INDEX ON listings(price);
CREATE INDEX ON listings(is_active);
CREATE INDEX ON price_snapshots(scraped_at);
CREATE INDEX ON price_snapshots(listing_id);
```

---

## Implementation Phases

---

### Phase 1 — Project Scaffold ✅ COMPLETE

**Claude:** Create repo structure, `requirements.txt`, `.env.example`, `.gitignore`

**Verify:** `python -c "import requests, bs4, psycopg2, streamlit"` — no import errors

**Note:** System uses Homebrew Python 3.14.5 with PEP 668 restrictions. Use a venv:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**Post-review fixes applied:**
- `schema.sql`: All `CREATE TABLE` → `CREATE TABLE IF NOT EXISTS` (idempotent; safe for CI re-runs)
- `schema.sql`: `price_per_sqm`/`size_sqm` → `NUMERIC(10,2)` (was `REAL`; avoids float precision loss)
- `schema.sql`: `first_seen`/`last_seen` → `NOT NULL DEFAULT CURRENT_DATE`
- `schema.sql`: `scrape_runs` counter columns → `DEFAULT 0` (avoids NULL in aggregates)
- `.gitignore`: Added `.env.*` (covers `.env.local`, `.env.prod`, etc.)
- `requirements.txt`: Added `lxml==5.2.2` (10–20× BeautifulSoup parse speedup)
- `requirements.txt`: Added `mypy==1.10.0` (required by CLAUDE.md for non-trivial logic)

---

### Phase 2 — Database Schema + DB Module ✅ COMPLETE

**Claude:** Write `schema.sql` and `scraper/db.py`

`db.py` functions:
- `get_connection()` — reads `DATABASE_URL` from env
- `upsert_listing(conn, listing)` — INSERT or UPDATE
- `record_snapshot(conn, listing_id, price, date)` — INSERT with UNIQUE guard
- `mark_delisted(conn, area, prop_type, seen_ids)` — set `is_active = FALSE` for absent IDs
- `log_scrape_run(conn, run_data)` — insert into scrape_runs

**Manual steps (user):** ✅ COMPLETE
1. Create project at supabase.com
2. SQL Editor → run `schema.sql`
3. Project Settings → Database → copy `DATABASE_URL`
4. Create local `.env`: `DATABASE_URL=postgresql://...`

**Verify:** `.venv/bin/python3 -c "from scraper.db import get_connection; get_connection(); print('OK')"` — no error

**Post-review fixes applied:**
- `schema.sql`: Indexes → `CREATE INDEX IF NOT EXISTS idx_name ON ...` (anonymous indexes crash on re-run; named + IF NOT EXISTS makes schema idempotent)
- `scraper/db.py`: `upsert_listing` — fixed `price_change` detection with CTE. `RETURNING listings.price` returns the post-update value (= new price), so the old comparison always returned False. CTE `WITH prev AS (SELECT price FROM listings WHERE id = ...)` captures old price before the upsert and returns it via `(SELECT price FROM prev)`.

---

### Phase 3 — Scraper Core ✅ COMPLETE

**Claude:** Write `scraper/config.py`, `scraper/fetcher.py`, `scraper/parser.py`

`config.py` — defines AREAS dict, PROPERTY_TYPES list, env-configurable request delays, BASE_URL pattern

`fetcher.py` — requests Session with realistic browser headers, `get_page(area, prop_type, page)` returns HTML, retries up to 3× on 429/5xx with exponential backoff

`parser.py` — `extract_listings(html)` parses JSON-LD `<script type="application/ld+json">` blocks (falls back to BeautifulSoup CSS selectors). Returns list of dicts: `id, price, price_per_sqm, size_sqm, bedrooms, location, condition, url`. UUID extracted from listing URL via regex.

**Verify:**
```bash
python -c "
from scraper.fetcher import get_page
from scraper.parser import extract_listings
html = get_page('matosinhos', 'apartamentos', 1)
print(len(extract_listings(html)), 'listings found')
"
```
Should print > 0.

**Deviations:**
- Casa Sapo has no JSON-LD. Parser uses `a.property-info` cards with onclick UUID extraction.
- Listing IDs are UUIDs from `Search.setLastSearch('...')` onclick attribute.
- Real listing URL decoded from `?l=` redirect param in href.
- Price format: Portuguese thousands separator (`.`) — "490.000 €" → 490000.

**Post-review fixes applied:**
- `scraper/fetcher.py`: Added `except requests.HTTPError: raise` before the `except requests.RequestException` block. `raise_for_status()` raises `HTTPError` (subclass of `RequestException`), so 404/403 responses were being silently retried 3× instead of failing fast.
- `scraper/parser.py`: Fixed `_parse_features` condition detection. Was `elif part and not size_sqm` — condition was silently dropped if size appeared before it in the `·`-delimited string. Now collects all non-size parts in a list and assigns condition after the loop, regardless of order.

---

### Phase 4 — Main Orchestrator ✅ COMPLETE

**Claude:** Write `main.py`

Loops all area × property type combinations, paginates until empty page, upserts each listing, records snapshots, marks delisted, logs run metadata to `scrape_runs`.

**Upsert logic:**
- New listing → INSERT + first snapshot
- Price changed → UPDATE price + INSERT snapshot (UNIQUE guards against duplicates on re-run)
- Price unchanged → UPDATE `last_seen` only
- Not seen this run → `is_active = FALSE`

**Verify (manual):**
1. `python main.py`
2. Check Supabase table browser — `listings` and `price_snapshots` populated
3. Run again — no duplicate snapshots, `last_seen` updated

**Implementation notes:**
- Commits per page (not per listing) — partial page loss on DB error, not entire combination
- `mark_delisted` uses human-readable `area_name` (matches `search_area` stored in DB)
- `MAX_PAGES = 100` hard cap on pagination (raised from 50 — Matosinhos/apartamentos, Matosinhos/luxo, Vila Nova de Gaia/apartamentos all hit the 50-page cap on first run)
- `for...else` on pagination loop emits `WARNING` when cap is hit — indicates truncated data without crashing
- mypy clean after installing `types-psycopg2` stubs

**Post-review fixes applied:**
- `main.py`: Wrapped all scraping + DB work in `try/finally` to guarantee `conn.close()` even on unhandled exceptions (previously connection leaked on any unexpected error)
- `main.py`: `except Exception` → `except (requests.RequestException, RuntimeError)` for fetch errors and `except psycopg2.Error` for DB errors — per CLAUDE.md "no bare except, always catch specific exceptions"
- `main.py`: `mark_delisted` + commit and `log_scrape_run` + commit were unguarded outside try/except — both now wrapped in `except psycopg2.Error` so a failure in either doesn't skip the other or leave the connection in a bad state
- `main.py`: Added `combo_had_error` flag per area × property-type combination — `mark_delisted` is skipped when any fetch or DB error occurred for that combo. Previously, a first-page fetch error left `seen_ids = {}` and the `else` branch of `mark_delisted` would deactivate *all* listings for the combo
- `scraper/db.py`: Removed `load_dotenv()` call (and its import) — `main.py` already calls it; side-effectful import made `db.py` hard to test in isolation
- `scraper/parser.py`: Removed unused `has_listings()` function — `main.py` uses `extract_listings()` + empty check directly
- `scraper/fetcher.py` + `scraper/parser.py`: All `Optional[X]` type hints → `X | None` (Python 3.10+ union syntax, consistent with 3.11+ requirement in CLAUDE.md)

---

### Phase 5 — GitHub Actions Workflow ✅ COMPLETE

**Claude:** Write `.github/workflows/scrape.yml`

```yaml
on:
  schedule:
    - cron: '0 3 * * 0'   # Weekly, Sunday 3am UTC
  workflow_dispatch:        # Manual trigger for testing

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          REQUEST_DELAY_MIN: 2
          REQUEST_DELAY_MAX: 5
```

**Manual steps (user):**
1. Push repo to GitHub
2. Repo Settings → Secrets → Actions → add `DATABASE_URL`
3. Actions tab → run workflow manually
4. Check Supabase table browser to confirm data arrived

---

### Phase 6 — Streamlit Dashboard ✅ COMPLETE

**Claude:** Write `dashboard/app.py`

**Sidebar filters:**
- Area (multi-select)
- Property type (multi-select)
- Bedrooms (multi-select: t0–t5+)
- Price range slider (EUR)
- Size range slider (m²)
- Active listings only toggle

**Views (tabs):**
1. **Listings table** — price, % change since first seen, size, bedrooms, area, type, link
2. **Price trends** — median price/m² over time, line chart per area × type
3. **Price movers** — top 20 drops and rises since first seen
4. **New listings** — first_seen = most recent scrape date
5. **Market volume** — listing count per area per week (stacked bar)

**Verify (local):**
1. `streamlit run dashboard/app.py`
2. All filters update table and charts
3. Listing links open Casa Sapo in browser

**Implementation notes:**
- `@st.cache_resource` for DB connection (persistent across reruns), `@st.cache_data(ttl=300)` for queries (5-min cache)
- `first_price` joined from `price_snapshots` on `first_seen` date; `price_change_pct` computed in Python
- Price trends tab computes per-snapshot `price/size_sqm` on the fly (listing size is static from `listings` table)
- Market volume uses `dt.to_period("W")` weekly bucketing, `nunique()` on `listing_id` to avoid double-counting same listing in multiple snapshots per week
- mypy clean with `--ignore-missing-imports` (stubs not needed for streamlit/plotly/pandas)

**Manual steps (user) — Streamlit Cloud deploy:**
1. share.streamlit.io → connect GitHub repo
2. Main file: `dashboard/app.py`
3. Add secret: `DATABASE_URL = postgresql://...`
4. Deploy

---

## Changing Scrape Frequency

The `UNIQUE (listing_id, scraped_at)` constraint makes all runs idempotent — safe to run multiple times per day.

| Frequency | cron value |
|-----------|-----------|
| Weekly (default) | `'0 3 * * 0'` |
| Daily | `'0 3 * * *'` |
| Twice daily | `'0 3,15 * * *'` |

Only `scrape.yml` needs editing. No schema or code changes required.

---

## Manual Steps Summary

| Step | After Phase | Action |
|------|-------------|--------|
| Create Supabase project + run schema.sql | Phase 2 | User |
| Create local `.env` with DATABASE_URL | Phase 2 | User |
| Push repo to GitHub | Phase 5 | User |
| Add DATABASE_URL secret to GitHub Actions | Phase 5 | User |
| Trigger workflow manually to test | Phase 5 | User |
| Deploy dashboard to Streamlit Cloud | Phase 6 | User |
| Add DATABASE_URL secret to Streamlit Cloud | Phase 6 | User |
