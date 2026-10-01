CREATE SCHEMA IF NOT EXISTS dp;

CREATE TABLE IF NOT EXISTS dp.pitchbook_deals (
  deal_id TEXT PRIMARY KEY,
  startup_id TEXT,
  startups TEXT NOT NULL,

  contains_cross_border BOOLEAN,
  add_on BOOLEAN,

  total_patent_documents BIGINT,
  total_patent_families BIGINT,
  active_patent_documents BIGINT,
  pending_patent_documents BIGINT,
  top_cpc_codes TEXT,

  current_employees BIGINT,
  hq_location TEXT,
  hq_global_region TEXT,
  hq_global_sub_region TEXT,
  company_city TEXT,
  company_state_province TEXT,
  company_post_code TEXT,
  company_country_region TEXT,
  company_website TEXT,
  year_founded BIGINT,

  revenue NUMERIC,
  net_income NUMERIC,
  ebitda NUMERIC,
  fiscal_year BIGINT,
  valuation_ebitda NUMERIC,
  valuation_net_income NUMERIC,
  valuation_revenue NUMERIC,
  deal_size_ebitda NUMERIC,
  deal_size_net_income NUMERIC,
  deal_size_revenue NUMERIC,
  ebitda_margin_pct NUMERIC,

  deal_no BIGINT,
  announced_date DATE,
  deal_date DATE,

  deal_size NUMERIC,
  deal_size_status TEXT,
  pre_money_valuation NUMERIC,
  post_valuation NUMERIC,
  post_valuation_status TEXT,
  percent_acquired NUMERIC,
  raised_to_date NUMERIC,
  native_currency_of_deal TEXT,
  total_invested_equity NUMERIC,

  vc_round TEXT,
  series TEXT,
  deal_type TEXT,
  deal_type_2 TEXT,
  deal_class TEXT,

  deal_synopsis TEXT,

  investors TEXT,
  investors_count BIGINT,
  investors_websites TEXT,
  new_investors TEXT,
  new_investors_count BIGINT,
  follow_on_investors TEXT,
  follow_on_investors_count BIGINT,
  lead_sole_investors TEXT,
  service_providers_all TEXT,
  service_providers_sell_side TEXT,

  description TEXT,
  financing_status TEXT,
  financing_status_note TEXT,
  business_status TEXT,
  primary_industry_sector TEXT,
  primary_industry_group TEXT,
  primary_industry_code TEXT,
  all_industries TEXT,
  verticals TEXT,
  keywords TEXT,
  emerging_spaces TEXT,
  current_financing_status TEXT,
  current_business_status TEXT,
  universe TEXT,

  ceo_pbid TEXT,
  ceo_at_time_of_deal TEXT,
  ceo_email TEXT,
  ceo_biography TEXT,
  ceo_education TEXT,

  view_company_online TEXT
);

CREATE INDEX IF NOT EXISTS idx_pitchbook_deals_startups
  ON dp.pitchbook_deals (startups);

CREATE INDEX IF NOT EXISTS idx_pitchbook_deals_deal_date
  ON dp.pitchbook_deals (deal_date);

CREATE INDEX IF NOT EXISTS idx_pitchbook_deals_announced_date
  ON dp.pitchbook_deals (announced_date);

CREATE INDEX IF NOT EXISTS idx_pitchbook_deals_deal_type
  ON dp.pitchbook_deals (deal_type);

CREATE INDEX IF NOT EXISTS idx_pitchbook_deals_company_country_region
  ON dp.pitchbook_deals (company_country_region);
