HEADER_MAP = {
    # Identities
    "Deal ID": "deal_id",
    "Company ID": "startup_id",
    "Companies": "startups",

    # Booleans
    "Contains Cross Border": "contains_cross_border",
    "Add-on": "add_on",

    # Patents / CPC
    "Total Patent Documents": "total_patent_documents",
    "Total Patent Families": "total_patent_families",
    "Active Patent Documents": "active_patent_documents",
    "Pending Patent Documents": "pending_patent_documents",
    "Top CPC Codes": "top_cpc_codes",

    # Location / profile
    "Current Employees": "current_employees",
    "HQ Location": "hq_location",
    "HQ Global Region": "hq_global_region",
    "HQ Global Sub Region": "hq_global_sub_region",
    "Company City": "company_city",
    "Company State/Province": "company_state_province",
    "Company Post Code": "company_post_code",
    "Company Country/Territory/Region": "company_country_region",
    "Company Website": "company_website",
    "Year Founded": "year_founded",

    # Financial metrics
    "Revenue": "revenue",
    "Net Income": "net_income",
    "EBITDA": "ebitda",
    "Fiscal Year": "fiscal_year",
    "Valuation/EBITDA": "valuation_ebitda",
    "Valuation/Net Income": "valuation_net_income",
    "Valuation/Revenue": "valuation_revenue",
    "Deal Size/EBITDA": "deal_size_ebitda",
    "Deal Size/Net Income": "deal_size_net_income",
    "Deal Size/Revenue": "deal_size_revenue",
    "EBITDA Margin %": "ebitda_margin_pct",

    # Deal identifiers / timing
    "Deal No.": "deal_no",
    "Announced Date": "announced_date",
    "Deal Date": "deal_date",

    # Deal amounts / valuation
    "Deal Size": "deal_size",
    "Deal Size Status": "deal_size_status",
    "Pre-money Valuation": "pre_money_valuation",
    "Post Valuation": "post_valuation",
    "Post Valuation Status": "post_valuation_status",
    "% Acquired": "percent_acquired",
    "Raised to Date": "raised_to_date",
    "Native Currency of Deal": "native_currency_of_deal",
    "Total Invested Equity": "total_invested_equity",

    # Classification
    "VC Round": "vc_round",
    "Series": "series",
    "Deal Type": "deal_type",
    "Deal Type 2": "deal_type_2",
    "Deal Class": "deal_class",

    # Narrative
    "Deal Synopsis": "deal_synopsis",

    # Parties
    "Investors": "investors",
    "# Investors": "investors_count",
    "Investors Websites": "investors_websites",
    "New Investors": "new_investors",
    "# New Investors": "new_investors_count",
    "Follow-on Investors": "follow_on_investors",
    "# Follow-on Investors": "follow_on_investors_count",
    "Lead/Sole Investors": "lead_sole_investors",
    "Service Providers (All)": "service_providers_all",
    "Service Providers (Sell-side)": "service_providers_sell_side",

    # Company descriptors / taxonomy
    "Description": "description",
    "Financing Status": "financing_status",
    "Financing Status Note": "financing_status_note",
    "Business Status": "business_status",
    "Primary Industry Sector": "primary_industry_sector",
    "Primary Industry Group": "primary_industry_group",
    "Primary Industry Code": "primary_industry_code",
    "All Industries": "all_industries",
    "Verticals": "verticals",
    "Keywords": "keywords",
    "Emerging Spaces": "emerging_spaces",
    "Current Financing Status": "current_financing_status",
    "Current Business Status": "current_business_status",
    "Universe": "universe",

    # CEO fields
    "CEO PBId": "ceo_pbid",
    "CEO (at time of deal)": "ceo_at_time_of_deal",
    "CEO Email": "ceo_email",
    "CEO Biography": "ceo_biography",
    "CEO Education": "ceo_education",

    # Links
    "View Company Online": "view_company_online",
}

# ── Company-profile export mapping ───────────────────────────────────────────
#
# HEADER_MAP_COMPANY maps every known PitchBook column header variant that can
# appear in a company-profile export → the corresponding dp.pitchbook_companies
# column name.
#
# PitchBook occasionally changes header wording between export versions (e.g.
# "Current Employees" vs "Employees", "Company Website" vs "Website").  All
# known variants are listed so that the ingest route accepts any of them.
#
HEADER_MAP_COMPANY: dict[str, str] = {

    # ── Identity ─────────────────────────────────────────────────────────────
    "Company ID":                           "company_id",
    # Primary company-name header variants
    "Companies":                            "company_name",   # standard export
    "Company Name":                         "company_name",   # alternate label
    "Company Legal Name":                   "company_legal_name",

    # ── Web presence ─────────────────────────────────────────────────────────
    "Company Website":                      "website",        # standard
    "Website":                              "website",        # short form
    "LinkedIn URL":                         "linkedin_url",   # standard
    "LinkedIn":                             "linkedin_url",   # short form

    # ── Primary contact ──────────────────────────────────────────────────────
    "Primary Contact":                      "primary_contact",
    "Primary Contact Title":                "primary_contact_title",
    "Primary Contact Email":                "primary_contact_email",
    "Primary Contact Phone":                "primary_contact_phone",

    # ── Company profile ──────────────────────────────────────────────────────
    "Description":                          "description",
    "Verticals":                            "verticals",
    "Keywords":                             "keywords",
    "Primary Industry Sector":              "primary_industry_sector",
    "Primary Industry Group":               "primary_industry_group",
    "Competitors":                          "competitors",
    "Opportunity Score":                    "opportunity_score",

    # ── Location — city ──────────────────────────────────────────────────────
    "Company City":                         "hq_city",        # standard
    "HQ City":                             "hq_city",        # alternate

    # ── Location — state/province ────────────────────────────────────────────
    "Company State/Province":               "hq_state_province",   # standard (no spaces)
    "HQ State/Province":                    "hq_state_province",   # alternate (no spaces)
    "HQ State / Province":                  "hq_state_province",   # alternate (spaces)

    # ── Location — country ───────────────────────────────────────────────────
    "Company Country/Territory/Region":     "hq_country_region",   # standard (no spaces)
    "Company Country / Territory / Region": "hq_country_region",   # standard (spaces)
    "HQ Country/Territory/Region":          "hq_country_region",   # alternate (no spaces)
    "HQ Country / Territory / Region":      "hq_country_region",   # alternate (spaces)

    # ── Location — global region ─────────────────────────────────────────────
    "HQ Global Region":                     "hq_global_region",

    # ── Headcount ────────────────────────────────────────────────────────────
    "Current Employees":                    "employees",      # standard
    "Employees":                            "employees",      # short form
    "Employee History":                     "employee_history",
    "Year Founded":                         "year_founded",

    # ── Financials ───────────────────────────────────────────────────────────
    "Revenue":                              "revenue",
    "Raised to Date":                       "total_raised",

    # ── Financing history ────────────────────────────────────────────────────
    "First Financing Deal Type 1":          "first_financing_deal_type_1",
    "First Financing Deal Class":           "first_financing_deal_class",
    "Last Financing Date":                  "last_financing_date",
    "Last Financing Size":                  "last_financing_size",
    "Last Financing Deal Type 1":           "last_financing_deal_type_1",
    "Last Financing Deal Class":            "last_financing_deal_class",

    # ── Investors ────────────────────────────────────────────────────────────
    "Active Investors":                     "active_investors",

    # ── Meta ─────────────────────────────────────────────────────────────────
    "Last Updated Date":                    "last_updated_date",
}