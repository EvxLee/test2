export type ColumnSource = "monday" | "pitchbook";

export type PartnerStartupColumn = {
  key: string;
  label: string;
  source: ColumnSource;

  getValue?: (row: any) => any;

  group?: "Monday.com" | "PitchBook";
};

const NA = "—";

/** Formats a PitchBook monetary value (stored in millions of USD) to a readable string.
 *  e.g. 5.2 -> "$5.2M", 1234.56 -> "$1.23B", 0.5 -> "$500K"
 */
function formatPitchbookMoney(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return NA;
  const n = Number(raw);
  if (isNaN(n)) return String(raw);
  if (n === 0) return "$0";
  if (n >= 1_000) return `$${(n / 1_000).toFixed(2)}B`;
  if (n >= 1) return `$${n % 1 === 0 ? n.toFixed(0) : n.toFixed(1)}M`;
  const k = n * 1_000;
  return `$${k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)}K`;
}

export const PARTNER_STARTUP_COLUMNS: PartnerStartupColumn[] = [
  // ---------------- Monday.com ----------------
  { key: "startups", label: "Company name", source: "monday", group: "Monday.com",
    getValue: (r) => r.startups || r.name || NA,
  },
  { key: "gced_cycle_year", label: "GCED Cycle & Year", source: "monday", group: "Monday.com",
    getValue: (r) => (r.gced_cycle && r.gced_cycle_year) ? `${r.gced_cycle} (${r.gced_cycle_year})` : (r.gced_cycle || r.gced_cycle_year || NA),
  },
  { key: "gced_track", label: "Track", source: "monday", group: "Monday.com" },
  { key: "gced_team_decision", label: "Decision", source: "monday", group: "Monday.com" },
  { key: "gced_startup_source", label: "Source", source: "monday", group: "Monday.com" },

  { key: "gced_cmbu_pjt", label: "CMBU PJT", source: "monday", group: "Monday.com" },
  { key: "gced_score_1", label: "Score 1 Overall Startup Strength", source: "monday", group: "Monday.com" },
  { key: "gced_score_2", label: "Score 2 Collaboration Potential", source: "monday", group: "Monday.com" },

  // ---------------- PitchBook ----------------
  { key: "company_website", label: "Website", source: "pitchbook", group: "PitchBook" },

  { key: "primary_contact", label: "Primary Contact", source: "pitchbook", group: "PitchBook" },
  { key: "primary_contact_title", label: "Primary Contact Title", source: "pitchbook", group: "PitchBook" },
  { key: "primary_contact_email", label: "Primary Contact Email", source: "pitchbook", group: "PitchBook" },
  { key: "primary_contact_phone", label: "Primary Contact Phone", source: "pitchbook", group: "PitchBook" },

  { key: "verticals", label: "Verticals", source: "pitchbook", group: "PitchBook" },
  { key: "description", label: "Description", source: "pitchbook", group: "PitchBook" },
  { key: "keywords", label: "Keywords", source: "pitchbook", group: "PitchBook" },
  { key: "revenue", label: "Revenue", source: "pitchbook", group: "PitchBook",
    getValue: (r) => formatPitchbookMoney(r.revenue),
  },
  { key: "raised_to_date", label: "Total Raised", source: "pitchbook", group: "PitchBook",
    getValue: (r) => formatPitchbookMoney(r.raised_to_date),
  },

  { key: "first_financing_deal_type_1", label: "First Financing Deal Type 1", source: "pitchbook", group: "PitchBook" },
  { key: "first_financing_deal_class", label: "First Financing Deal Class", source: "pitchbook", group: "PitchBook" },
  { key: "last_financing_date", label: "Last Financing Date", source: "pitchbook", group: "PitchBook",
    getValue: (r) => r.last_financing_date || r.deal_date || r.announced_date || NA,
  },
  { key: "last_financing_size", label: "Last Financing Size", source: "pitchbook", group: "PitchBook",
    getValue: (r) => formatPitchbookMoney(r.last_financing_size ?? r.deal_size),
  },
  { key: "last_financing_deal_type_1", label: "Last Financing Deal Type 1", source: "pitchbook", group: "PitchBook",
    getValue: (r) => r.last_financing_deal_type_1 || r.deal_type || NA,
  },
  { key: "last_financing_deal_class", label: "Last Financing Deal Class", source: "pitchbook", group: "PitchBook",
    getValue: (r) => r.last_financing_deal_class || r.deal_class || NA,
  },

  { key: "investors", label: "Active Investors", source: "pitchbook", group: "PitchBook" },

  { key: "company_state_province", label: "HQ State / Province", source: "pitchbook", group: "PitchBook" },
  { key: "company_city", label: "HQ City", source: "pitchbook", group: "PitchBook" },
  { key: "company_country_region", label: "HQ Country / Territory / Region", source: "pitchbook", group: "PitchBook" },
  { key: "hq_global_region", label: "HQ Global Region", source: "pitchbook", group: "PitchBook" },

  { key: "opportunity_score", label: "Opportunity Score", source: "pitchbook", group: "PitchBook" },
  { key: "company_legal_name", label: "Company Legal Name", source: "pitchbook", group: "PitchBook" },
  { key: "competitors", label: "Competitors", source: "pitchbook", group: "PitchBook" },

  { key: "primary_industry_sector", label: "Primary Industry Sector", source: "pitchbook", group: "PitchBook" },
  { key: "primary_industry_group", label: "Primary Industry Group", source: "pitchbook", group: "PitchBook" },

  { key: "linkedin_url", label: "LinkedIn URL", source: "pitchbook", group: "PitchBook" },

  { key: "current_employees", label: "Employees", source: "pitchbook", group: "PitchBook" },

  { key: "employee_history", label: "Employee History", source: "pitchbook", group: "PitchBook" },

  { key: "year_founded", label: "Year Founded", source: "pitchbook", group: "PitchBook" },

  { key: "last_updated_date", label: "Last Updated Date", source: "pitchbook", group: "PitchBook" },
];
