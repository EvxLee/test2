CREATE SCHEMA IF NOT EXISTS startups_pitchbook;

CREATE TABLE IF NOT EXISTS startups_pitchbook.pitchbook (
  deal_id TEXT PRIMARY KEY,
  company_id TEXT,
  companies TEXT NOT NULL,
  contains_cross_border BOOLEAN,
  add_on BOOLEAN,
  total_patent_documents INT,
  total_patent_families INT,
  active_patent_documents INT,
  pending_patent_documents INT,
  top_cpc_codes TEXT,
  current_employees INT,
  hq_location TEXT,
  hq_global_region TEXT,
  hq_global_sub_region TEXT,
  company_city TEXT,
  company_state_province TEXT,
  company_post_code TEXT,
  company_country_region TEXT,
  company_website TEXT,
  year_founded INT,
  revenue NUMERIC,
  net_income NUMERIC,
  ebitda NUMERIC,
  fiscal_year INT,
  valuation_ebitda NUMERIC,
  valuation_net_income NUMERIC,
  valuation_revenue NUMERIC,
  deal_size_ebitda NUMERIC,
  deal_size_net_income NUMERIC,
  deal_size_revenue NUMERIC,
  ebitda_margin_pct NUMERIC,
  deal_no INT,
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
  investors_count INT,
  investors_websites TEXT,
  new_investors TEXT,
  new_investors_count INT,
  follow_on_investors TEXT,
  follow_on_investors_count INT,
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


CREATE INDEX IF NOT EXISTS ix_pitchbook_companies
  ON startups_pitchbook.pitchbook (companies);

CREATE INDEX IF NOT EXISTS ix_pitchbook_deal_date
  ON startups_pitchbook.pitchbook (deal_date);

CREATE INDEX IF NOT EXISTS ix_pitchbook_announced_date
  ON startups_pitchbook.pitchbook (announced_date);

CREATE INDEX IF NOT EXISTS ix_pitchbook_deal_type
  ON startups_pitchbook.pitchbook (deal_type);

CREATE INDEX IF NOT EXISTS ix_pitchbook_company_country
  ON startups_pitchbook.pitchbook (company_country_region);
