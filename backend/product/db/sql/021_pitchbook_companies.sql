-- dp.pitchbook_companies
-- Stores company-level PitchBook export data (company profile export format).
-- Primary key: company_id (PitchBook's internal company identifier).
--
-- Only columns required by the Partner Startups UI are stored here.
-- The existing dp.pitchbook_deals table (deal-level export) is kept as-is for
-- backwards compatibility but does not need new work going forward.

CREATE TABLE IF NOT EXISTS dp.pitchbook_companies (

  -- ── Identity ─────────────────────────────────────────────────────────────
  company_id            TEXT PRIMARY KEY,   -- PitchBook company identifier
  company_name          TEXT NOT NULL,
  company_legal_name    TEXT,

  -- ── Online presence ──────────────────────────────────────────────────────
  website               TEXT,
  linkedin_url          TEXT,

  -- ── Primary contact ──────────────────────────────────────────────────────
  primary_contact       TEXT,
  primary_contact_title TEXT,
  primary_contact_email TEXT,
  primary_contact_phone TEXT,

  -- ── Description & classification ─────────────────────────────────────────
  description           TEXT,
  verticals             TEXT,
  keywords              TEXT,
  primary_industry_sector TEXT,
  primary_industry_group  TEXT,
  competitors           TEXT,

  -- ── Financials ───────────────────────────────────────────────────────────
  revenue               NUMERIC,
  total_raised          NUMERIC,

  first_financing_deal_type_1  TEXT,
  first_financing_deal_class   TEXT,

  last_financing_date          DATE,
  last_financing_size          NUMERIC,
  last_financing_deal_type_1   TEXT,
  last_financing_deal_class    TEXT,

  active_investors      TEXT,

  -- ── Headcount & history ──────────────────────────────────────────────────
  employees             BIGINT,
  employee_history      TEXT,
  year_founded          INT,

  -- ── HQ location ──────────────────────────────────────────────────────────
  hq_city               TEXT,
  hq_state_province     TEXT,
  hq_country_region     TEXT,   -- covers "Company Country/Territory/Region" and variants
  hq_global_region      TEXT,

  -- ── Scoring & dates ──────────────────────────────────────────────────────
  opportunity_score     NUMERIC,
  last_updated_date     DATE,

  -- ── Ingest metadata ──────────────────────────────────────────────────────
  ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_pb_companies_name
  ON dp.pitchbook_companies (company_name);

CREATE INDEX IF NOT EXISTS idx_pb_companies_hq_country
  ON dp.pitchbook_companies (hq_country_region);

CREATE INDEX IF NOT EXISTS idx_pb_companies_hq_global_region
  ON dp.pitchbook_companies (hq_global_region);

CREATE INDEX IF NOT EXISTS idx_pb_companies_primary_industry_sector
  ON dp.pitchbook_companies (primary_industry_sector);

CREATE INDEX IF NOT EXISTS idx_pb_companies_year_founded
  ON dp.pitchbook_companies (year_founded);

CREATE INDEX IF NOT EXISTS idx_pb_companies_last_financing_date
  ON dp.pitchbook_companies (last_financing_date);

CREATE INDEX IF NOT EXISTS idx_pb_companies_updated_at
  ON dp.pitchbook_companies (updated_at DESC);
