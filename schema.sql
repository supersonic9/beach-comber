CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    property_type   TEXT NOT NULL,
    search_area     TEXT NOT NULL,
    location        TEXT,
    bedrooms        TEXT,
    price           INTEGER,
    price_per_sqm   NUMERIC(10,2),
    size_sqm        NUMERIC(10,2),
    condition       TEXT,
    url             TEXT,
    first_seen      DATE NOT NULL DEFAULT CURRENT_DATE,
    last_seen       DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id          SERIAL PRIMARY KEY,
    listing_id  TEXT NOT NULL REFERENCES listings(id),
    scraped_at  DATE NOT NULL,
    price       INTEGER,
    UNIQUE (listing_id, scraped_at)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    total_listings  INTEGER DEFAULT 0,
    new_listings    INTEGER DEFAULT 0,
    price_changes   INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_listings_property_type ON listings(property_type);
CREATE INDEX IF NOT EXISTS idx_listings_search_area ON listings(search_area);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_is_active ON listings(is_active);
CREATE INDEX IF NOT EXISTS idx_snapshots_scraped_at ON price_snapshots(scraped_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_listing_id ON price_snapshots(listing_id);
