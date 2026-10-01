import React, { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import SearchBar from "app/components/Searchbar";
import KeywordSearch from "app/components/KeywordSearch";
import StartupCard from "app/components/Startupcards";
import FilterBar from "app/components/Filter";
import StartupDetailPanel from "app/components/StartupDetailPanel";
import { PARTNER_STARTUP_COLUMNS } from "app/lib/partnerStartupColumns";
import { findStartupByName } from "app/lib/findStartupByName";
import { useBoardConfig } from "app/lib/useBoardConfig";


const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

function normalizeKey(v?: string | null): string {
  return (v || "").toLowerCase().trim();
}

function normalizeNameKey(v?: string | null): string {
  return normalizeKey(v).replace(/[^a-z0-9]/g, "");
}

function hasValue(v: any): boolean {
  return v !== null && v !== undefined && v !== "";
}

function coalesce(companyVal: any, dealVal: any) {
  return hasValue(companyVal) ? companyVal : dealVal;
}

function mergeRowsPreferNonEmpty(a: StartupRow, b: StartupRow): StartupRow {
  const result: StartupRow = { ...a };
  Object.keys(b).forEach((k) => {
    const key = k as keyof StartupRow;
    const aVal = result[key];
    const bVal = b[key];
    if (!hasValue(aVal) && hasValue(bVal)) {
      (result as any)[key] = bVal;
    }
  });
  result.has_pitchbook_data = Boolean(a.has_pitchbook_data || b.has_pitchbook_data);
  result.has_gced_match = Boolean(a.has_gced_match || b.has_gced_match);
  return result;
}

async function fetchAllDisplayRows<T>(
  baseUrl: string,
  authHeader: Record<string, string>
): Promise<T[]> {
  let allRows: T[] = [];
  let cursor: string | null = null;
  let hasMore = true;

  while (hasMore) {
    let url = baseUrl;
    if (cursor) url += `&cursor=${encodeURIComponent(cursor)}`;

    const res = await fetch(url, { headers: authHeader });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Failed to fetch ${url}: ${res.status} ${res.statusText} ${body}`);
    }

    const json = await res.json();
    const rows = (json.rows || []) as T[];
    allRows = [...allRows, ...rows];

    if (json.next_cursor) {
      cursor = json.next_cursor;
    } else {
      hasMore = false;
    }
  }

  return allRows;
}

interface PartnerStartupRow {
  startup_name?: string;
  project_id?: string;
}

interface ProjectRow {
  id?: string;
  name?: string;
}

// Helper to fetch all GCED rows with pagination
async function fetchAllGCED(baseUrl: string, authHeader: Record<string, string>): Promise<GCEDRow[]> {
  return fetchAllDisplayRows<GCEDRow>(baseUrl, authHeader);
}

// PitchBook deals data
interface PitchBookRow {
  pb_company_id?: string;
  pb_company_name?: string;

  deal_id?: string;
  startup_id?: string;
  startups?: string;

  contains_cross_border?: boolean | string | null;
  add_on?: boolean | string | null;

  total_patent_documents?: number | string | null;
  total_patent_families?: number | string | null;
  active_patent_documents?: number | string | null;
  pending_patent_documents?: number | string | null;
  top_cpc_codes?: string | null;

  current_employees?: number | string | null;
  hq_location?: string | null;
  hq_global_region?: string | null;
  hq_global_sub_region?: string | null;
  company_city?: string | null;
  company_state_province?: string | null;
  company_post_code?: string | null;
  company_country_region?: string | null;
  company_website?: string | null;
  year_founded?: number | string | null;

  revenue?: string | null;
  net_income?: string | null;
  ebitda?: string | null;
  fiscal_year?: string | null;
  valuation_ebitda?: string | null;
  valuation_net_income?: string | null;
  valuation_revenue?: string | null;
  deal_size_ebitda?: string | null;
  deal_size_net_income?: string | null;
  deal_size_revenue?: string | null;
  ebitda_margin_pct?: string | null;

  deal_no?: string | null;
  announced_date?: string | null;
  deal_date?: string | null;

  deal_size?: string | null;
  deal_size_status?: string | null;
  pre_money_valuation?: string | null;
  post_valuation?: string | null;
  post_valuation_status?: string | null;
  percent_acquired?: string | null;
  raised_to_date?: string | null;
  native_currency_of_deal?: string | null;
  total_invested_equity?: string | null;

  vc_round?: string | null;
  series?: string | null;
  deal_type?: string | null;
  deal_type_2?: string | null;
  deal_class?: string | null;

  deal_synopsis?: string | null;

  investors?: string | null;
  investors_count?: number | string | null;
  investors_websites?: string | null;
  new_investors?: string | null;
  new_investors_count?: number | string | null;
  follow_on_investors?: string | null;
  follow_on_investors_count?: number | string | null;
  lead_sole_investors?: string | null;
  service_providers_all?: string | null;
  service_providers_sell_side?: string | null;

  description?: string | null;
  financing_status?: string | null;
  financing_status_note?: string | null;
  business_status?: string | null;
  primary_industry_sector?: string | null;
  primary_industry_group?: string | null;
  primary_industry_code?: string | null;
  all_industries?: string | null;
  verticals?: string | null;
  keywords?: string | null;
  emerging_spaces?: string | null;
  current_financing_status?: string | null;
  current_business_status?: string | null;
  universe?: string | null;

  ceo_pbid?: string | null;
  ceo_at_time_of_deal?: string | null;
  ceo_email?: string | null;
  ceo_biography?: string | null;
  ceo_education?: string | null;

  view_company_online?: string | null;

  [key: string]: any;
}

function normalizeCompanyRow(c: any): PitchBookRow {
  return {
    ...c,
    pb_company_id: c.company_id,
    pb_company_name: c.company_name,
    startup_id: c.company_id,
    startups: c.company_name,
    company_website: c.website,
    raised_to_date: c.total_raised,
    investors: c.active_investors,
    current_employees: c.employees,
    company_city: c.hq_city,
    company_state_province: c.hq_state_province,
    company_country_region: c.hq_country_region,
  };
}

function normalizeDealRow(d: any): PitchBookRow {
  return {
    ...d,
    startup_id: hasValue(d.startup_id) ? String(d.startup_id).trim() : d.startup_id,
    startups: hasValue(d.startups) ? String(d.startups).trim() : d.startups,
  };
}

// GCED MFTF25 startups data
interface GCEDRow {
  id?: string;
  source?: string;
  monday_board_id?: string;
  monday_item_id?: string;
  monday_item_name?: string;
  startup_name?: string;
  hubspot_link?: string | null;
  switchpitch_link?: string | null;
  startup_source?: string | null;
  track?: string | null;
  startup_type?: string | null;
  gced_scrub_label?: string | null;
  team_decision?: string | null;
  pitch_deck_rec?: string | null;
  sosa_status?: string | null;
  average_score?: number | string | null;
  overall_startup_strength?: number | string | null;
  collaboration_potential?: number | string | null;
  due_date?: string | null;
  last_updated_at?: string | null;
  pre_cap_notes?: string | null;
  people_label?: string | null;
  team_label?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: any;
}

// Combined data from both sources
interface StartupRow extends PitchBookRow {
  // GCED fields merged in
  gced_id?: string;
  gced_monday_board_id?: string;
  gced_monday_item_id?: string;
  gced_monday_item_name?: string;
  gced_startup_name?: string;
  gced_hubspot_link?: string | null;
  gced_switchpitch_link?: string | null;
  gced_startup_source?: string | null;
  gced_track?: string | null;
  gced_startup_type?: string | null;
  gced_scrub_label?: string | null;
  gced_team_decision?: string | null;
  gced_pitch_deck_rec?: string | null;
  gced_sosa_status?: string | null;
  gced_average_score?: number | string | null;
  gced_due_date?: string | null;
  gced_last_updated_at?: string | null;
  gced_pre_cap_notes?: string | null;
  gced_people_label?: string | null;
  gced_team_label?: string | null;
  gced_cycle?: string | null;
  gced_cycle_year?: number | null;
  gced_score_1?: number | null;
  gced_score_2?: number | null;
  has_gced_match?: boolean;
  has_pitchbook_data?: boolean;
  incubation_cmbu_label?: string | null;
}

interface StartupDisplay extends StartupRow {
  id: string;
  name: string;

  track: string;
  stage: string;
  stageLevel: string;
  country: string;
  continent: string;
  founded: number | null;
  totalRaised: string;
  minEmployees: number | null;
  maxEmployees: number | null;

  status: "Ongoing" | "On Hold" | "Archived" | null;
  shortDesc: string;
  profilePics: string[];
  associatedProjectName: string;
}

export default function PartnerStartups() {
  const { gcedCycles, projectBoardFilter } = useBoardConfig();
  const boardToCycleMap = useMemo(() => {
    const map = new Map<string, { label: string; year: number }>();
    gcedCycles.forEach((c) => map.set(c.boardId, { label: c.label, year: c.year }));
    return map;
  }, [gcedCycles]);

  const [query, setQuery] = useState("");
  const [keywordTags, setKeywordTags] = useState<string[]>([]);
  const [selectedStartup, setSelectedStartup] = useState<StartupDisplay | null>(
    null
  );
  const [filters, setFilters] = useState<any>({});
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");

  const [startups, setStartups] = useState<StartupDisplay[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchParams] = useSearchParams();
  const hasAutoSelected = useRef(false);

  // Auto-select a startup when navigated here with ?startup=<name>.
  // Fires once after data loads — searchParams is read but intentionally not reactive.
  useEffect(() => {
    if (hasAutoSelected.current) return;
    if (isLoading || startups.length === 0) return;

    const targetName = searchParams.get("startup");
    if (targetName) {
      const match = findStartupByName(startups, targetName);
      if (match) setSelectedStartup(match);
    }
    hasAutoSelected.current = true;
  }, [startups, isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // keep header + filters visible when switching view
  useEffect(() => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [viewMode]);

  useEffect(() => {
    async function load() {
      const authHeader = {
        Authorization: `Bearer ${API_TOKEN}`,
      };

      // pitchbook_companies — primary source, rich company-level data
      const companiesColumns = [
        "company_id",
        "company_name",
        "company_legal_name",
        "website",
        "linkedin_url",
        "primary_contact",
        "primary_contact_title",
        "primary_contact_email",
        "primary_contact_phone",
        "description",
        "verticals",
        "keywords",
        "primary_industry_sector",
        "primary_industry_group",
        "competitors",
        "revenue",
        "total_raised",
        "first_financing_deal_type_1",
        "first_financing_deal_class",
        "last_financing_date",
        "last_financing_size",
        "last_financing_deal_type_1",
        "last_financing_deal_class",
        "active_investors",
        "employees",
        "employee_history",
        "year_founded",
        "hq_city",
        "hq_state_province",
        "hq_country_region",
        "hq_global_region",
        "opportunity_score",
        "last_updated_date",
      ].join(",");

      // pitchbook_deals — deal IDs, deal-specific fields, and company profile fields present in deals
      const dealsColumns = [
        "deal_id",
        "startup_id",
        "startups",
        // Deal-specific
        "deal_date",
        "announced_date",
        "deal_size",
        "deal_type",
        "deal_class",
        "deal_synopsis",
        // Company profile fields also present in deals (used as fallback)
        "company_website",
        "current_employees",
        "company_city",
        "company_state_province",
        "company_country_region",
        "hq_global_region",
        "year_founded",
        "revenue",
        "raised_to_date",
        "investors",
        "description",
        "verticals",
        "keywords",
        "primary_industry_sector",
        "primary_industry_group",
      ].join(",");


      const companiesUrl = `${BASE_URL}/atlas/display/data?schema=dp&redact=off&table=pitchbook_companies&columns=${companiesColumns}&limit=500`;
      const dealsUrl = `${BASE_URL}/atlas/display/data?schema=dp&redact=off&table=pitchbook_deals&columns=${dealsColumns}&limit=500`;
      const gcedUrl = `${BASE_URL}/atlas/display/data?schema=master_dashboard&table=gced_mftf25_startups&redact=off&limit=500`;
      const partnerStartupsUrl = `${BASE_URL}/atlas/display/data?schema=master_dashboard&table=project_partner_startups&redact=off&columns=startup_name,project_id&limit=500`;
      const projectsUrl = `${BASE_URL}/atlas/display/data?schema=master_dashboard&table=projects&redact=off&columns=id,name&limit=500&filter=${encodeURIComponent(projectBoardFilter)}`;

      try {
        setIsLoading(true);
        setError(null);

        // Fetch all five sources in parallel
        const [rawCompanyRows, rawDealRows, gcedRows, partnerStartupRows, projectRows] = await Promise.all([
          fetchAllDisplayRows<any>(companiesUrl, authHeader),
          fetchAllDisplayRows<any>(dealsUrl, authHeader),
          fetchAllGCED(gcedUrl, authHeader),
          fetchAllDisplayRows<PartnerStartupRow>(partnerStartupsUrl, authHeader),
          fetchAllDisplayRows<ProjectRow>(projectsUrl, authHeader),
        ]);


        const companyRows = rawCompanyRows.map((c) => normalizeCompanyRow(c));
        const dealRows = rawDealRows.map((d) => normalizeDealRow(d));
        // Build deal lookup by startup_id (primary) and startup name (fallback)
        const dealByStartupId = new Map<string, PitchBookRow>();
        const dealByName = new Map<string, PitchBookRow>();
        dealRows.forEach((d) => {
          const id = normalizeKey(d.startup_id);
          const name = normalizeNameKey(d.startups);
          if (id && !dealByStartupId.has(id)) dealByStartupId.set(id, d);
          if (name && !dealByName.has(name)) dealByName.set(name, d);
        });
        const processedIds = new Set<string>();
        const processedNames = new Set<string>();
        const pitchbookRows: PitchBookRow[] = [];

        companyRows.forEach((co) => {
          const companyId = normalizeKey(co.pb_company_id || co.startup_id);
          const name = normalizeNameKey(co.pb_company_name || co.startups);
          if (companyId) processedIds.add(companyId);
          if (name) processedNames.add(name);

          const deal =
            (companyId ? dealByStartupId.get(companyId) : undefined) ||
            (name ? dealByName.get(name) : undefined);

          pitchbookRows.push({
            ...(deal || {}),
            ...co,
            company_website: coalesce(co.company_website, deal?.company_website),
            current_employees: coalesce(co.current_employees, deal?.current_employees),
            company_city: coalesce(co.company_city, deal?.company_city),
            company_state_province: coalesce(co.company_state_province, deal?.company_state_province),
            company_country_region: coalesce(co.company_country_region, deal?.company_country_region),
            hq_global_region: coalesce(co.hq_global_region, deal?.hq_global_region),
            year_founded: coalesce(co.year_founded, deal?.year_founded),
            revenue: coalesce(co.revenue, deal?.revenue),
            raised_to_date: coalesce(co.raised_to_date, deal?.raised_to_date),
            investors: coalesce(co.investors, deal?.investors),
            description: coalesce(co.description, deal?.description),
            verticals: coalesce(co.verticals, deal?.verticals),
            keywords: coalesce(co.keywords, deal?.keywords),
            primary_industry_sector: coalesce(co.primary_industry_sector, deal?.primary_industry_sector),
            primary_industry_group: coalesce(co.primary_industry_group, deal?.primary_industry_group),
            // Deal IDs and deal-only fields (always from deal)
            deal_id: deal?.deal_id,
            startup_id: deal?.startup_id || co.startup_id,
            deal_date: deal?.deal_date,
            announced_date: deal?.announced_date,
            deal_size: deal?.deal_size,
            deal_type: deal?.deal_type,
            deal_class: deal?.deal_class,
            deal_synopsis: deal?.deal_synopsis,
          });
        });

        // Add deal-only rows (startups in deals with no company match yet)
        dealRows.forEach((d) => {
          const id = normalizeKey(d.startup_id);
          const name = normalizeNameKey(d.startups);
          const matchedById = id && processedIds.has(id);
          const matchedByName = name && processedNames.has(name);
          if (!matchedById && !matchedByName) pitchbookRows.push({ ...d });
        });

        // Build project name lookup: project_id → project name
        const projectNameById = new Map<string, string>();
        projectRows.forEach((p) => {
          if (p.id && p.name) projectNameById.set(p.id, p.name);
        });

        // Build project name lookup: normalized startup name → project name
        const projectNameByStartupName = new Map<string, string>();
        partnerStartupRows.forEach((ps) => {
          const name = (ps.startup_name || "").toLowerCase().trim();
          const projectName = ps.project_id ? projectNameById.get(ps.project_id) : undefined;
          if (name && projectName && !projectNameByStartupName.has(name)) {
            projectNameByStartupName.set(name, projectName);
          }
        });
        // Build GCED lookup map by normalized startup name
        const gcedByName = new Map<string, GCEDRow>();
        gcedRows.forEach((gced) => {
          const name = normalizeNameKey(gced.startup_name || gced.monday_item_name);
          if (name) {
            gcedByName.set(name, gced);
          }
        });

        // Merge PitchBook rows with GCED data
        const mergedRows: StartupRow[] = pitchbookRows.map((pb) => {
          const pbName = normalizeNameKey(pb.startups);
          const gcedMatch = gcedByName.get(pbName);

          if (gcedMatch) {
            const cycleInfo = boardToCycleMap.get(gcedMatch.monday_board_id || "");
            return {
              ...pb,
              gced_id: gcedMatch.id,
              gced_monday_board_id: gcedMatch.monday_board_id,
              gced_monday_item_id: gcedMatch.monday_item_id,
              gced_monday_item_name: gcedMatch.monday_item_name,
              gced_startup_name: gcedMatch.startup_name,
              gced_hubspot_link: gcedMatch.hubspot_link,
              gced_switchpitch_link: gcedMatch.switchpitch_link,
              gced_startup_source: gcedMatch.startup_source,
              gced_track: gcedMatch.track,
              gced_startup_type: gcedMatch.startup_type,
              gced_scrub_label: gcedMatch.gced_scrub_label,
              gced_team_decision: gcedMatch.team_decision,
              gced_pitch_deck_rec: gcedMatch.pitch_deck_rec,
              gced_sosa_status: gcedMatch.sosa_status,
              gced_average_score: gcedMatch.average_score,
              gced_due_date: gcedMatch.due_date,
              gced_last_updated_at: gcedMatch.last_updated_at,
              gced_pre_cap_notes: gcedMatch.pre_cap_notes,
              gced_people_label: gcedMatch.people_label,
              gced_team_label: gcedMatch.team_label,
              gced_cycle: cycleInfo?.label || null,
              gced_cycle_year: cycleInfo?.year || null,
              gced_score_1: gcedMatch.overall_startup_strength != null ? Number(gcedMatch.overall_startup_strength) : null,
              gced_score_2: gcedMatch.collaboration_potential != null ? Number(gcedMatch.collaboration_potential) : null,
              has_gced_match: true,
              has_pitchbook_data: true,
              incubation_cmbu_label: projectNameByStartupName.get(pbName) || null,
            };
          }
          return {
            ...pb,
            has_gced_match: false,
            has_pitchbook_data: true,
            incubation_cmbu_label: projectNameByStartupName.get(pbName) || null,
          };
        });

        // Also add GCED-only startups that aren't in PitchBook
        const pitchbookNames = new Set(
          pitchbookRows.map((pb) => normalizeNameKey(pb.startups))
        );
        gcedRows.forEach((gced) => {
          const gcedName = normalizeNameKey(gced.startup_name || gced.monday_item_name);
          if (gcedName && !pitchbookNames.has(gcedName)) {
            const cycleInfo = boardToCycleMap.get(gced.monday_board_id || "");
            mergedRows.push({
              startups: gced.startup_name || gced.monday_item_name,
              gced_id: gced.id,
              gced_monday_board_id: gced.monday_board_id,
              gced_monday_item_id: gced.monday_item_id,
              gced_monday_item_name: gced.monday_item_name,
              gced_startup_name: gced.startup_name,
              gced_hubspot_link: gced.hubspot_link,
              gced_switchpitch_link: gced.switchpitch_link,
              gced_startup_source: gced.startup_source,
              gced_track: gced.track,
              gced_startup_type: gced.startup_type,
              gced_scrub_label: gced.gced_scrub_label,
              gced_team_decision: gced.team_decision,
              gced_pitch_deck_rec: gced.pitch_deck_rec,
              gced_sosa_status: gced.sosa_status,
              gced_average_score: gced.average_score,
              gced_due_date: gced.due_date,
              gced_last_updated_at: gced.last_updated_at,
              gced_pre_cap_notes: gced.pre_cap_notes,
              gced_people_label: gced.people_label,
              gced_team_label: gced.team_label,
              gced_cycle: cycleInfo?.label || null,
              gced_cycle_year: cycleInfo?.year || null,
              gced_score_1: gced.overall_startup_strength != null ? Number(gced.overall_startup_strength) : null,
              gced_score_2: gced.collaboration_potential != null ? Number(gced.collaboration_potential) : null,
              has_gced_match: true,
              has_pitchbook_data: false,
              incubation_cmbu_label: projectNameByStartupName.get(gcedName) || null,
            });
          }
        });

        // Deduplicate near-duplicate startup names and keep non-empty data from both rows.
        const byName = new Map<string, StartupRow>();
        mergedRows.forEach((row) => {
          const key = normalizeNameKey(row.startups || row.gced_startup_name || row.gced_monday_item_name);
          if (!key) return;
          const existing = byName.get(key);
          if (!existing) {
            byName.set(key, row);
            return;
          }
          byName.set(key, mergeRowsPreferNonEmpty(existing, row));
        });

        const rows = Array.from(byName.values());

        const mapped: StartupDisplay[] = rows.map((row, idx) => {

          const id = String(row.deal_id || row.startup_id || row.pb_company_id || idx);
          const name = row.startups || "Unknown Company";

          const industry =
            row.primary_industry_sector ||
            row.verticals ||
            row.primary_industry_group ||
            "";

          const stageName =
            row.series ||
            row.vc_round ||
            row.current_financing_status ||
            row.financing_status ||
            "";

          const country = row.company_country_region || "";
          const continent = row.hq_global_region || "";
          const foundedYear = row.year_founded
            ? Number(row.year_founded)
            : null;

          const totalRaised = row.raised_to_date || row.deal_size || "";
          const minEmployees = row.current_employees
            ? Number(row.current_employees)
            : null;
          const maxEmployees = minEmployees ?? null;

          const statusRaw =
            row.current_business_status || row.business_status || "";
          const normalizedStatus = statusRaw.toLowerCase();
          let status: StartupDisplay["status"] = null;
          if (normalizedStatus) {
            if (
              normalizedStatus.includes("closed") ||
              normalizedStatus.includes("out of business") ||
              normalizedStatus.includes("acquired")
            ) {
              status = "Archived";
            } else if (normalizedStatus.includes("operat")) {
              status = "Ongoing";
            } else {
              status = "On Hold";
            }
          }

          const shortDesc =
            row.deal_synopsis ||
            row.description ||
            "No description available.";

          // 1) gced_mftf25_startups.team_label — use when non-blank and not a
          //    generic decision value (yes / no / yes for later / additional review)
          const GENERIC_GCED_LABELS = new Set([
            "yes", "no", "yes for later", "additional review",
          ]);
          const teamLabelRaw = (row.gced_team_label || "").trim();
          const teamLabelProject =
            teamLabelRaw && !GENERIC_GCED_LABELS.has(teamLabelRaw.toLowerCase())
              ? teamLabelRaw
              : "";

          // 2) incubation_startups.cmbu_label — matched by startup name
          const cmbuLabel = (row.incubation_cmbu_label || "").trim();

          const associatedProjectName = cmbuLabel || teamLabelProject || "N/A";

          const avatarBase = encodeURIComponent(name || "Startup");
          const profilePics = [
            `https://ui-avatars.com/api/?name=${avatarBase}&background=8B1E2F&color=fff`,
            `https://ui-avatars.com/api/?name=${avatarBase}&background=F97316&color=fff`,
          ];

          const display: StartupDisplay = {
            ...row,
            id,
            name,
            track: industry,
            stage: stageName,
            stageLevel: stageName,
            country,
            continent,
            founded: foundedYear,
            totalRaised,
            minEmployees,
            maxEmployees,
            status,
            shortDesc,
            profilePics,
            associatedProjectName,
            gced_cmbu_pjt: associatedProjectName !== "N/A" ? associatedProjectName : null,
          };

          return display;
        });

        setStartups(mapped);
      } catch (err: any) {
        console.error("[PartnerStartups] Error loading startups:", err);
        setError(err?.message || "Unknown error while loading startups.");
      } finally {
        setIsLoading(false);
      }
    }

    load();
  }, [boardToCycleMap, projectBoardFilter]);
const exportToCSV = () => {
  if (!filteredStartups.length) return;

  // create header row
  const headers = PARTNER_STARTUP_COLUMNS.map((col) => col.label).join(",");

  // create data rows
  const rows = filteredStartups.map((startup) =>
    PARTNER_STARTUP_COLUMNS.map((col) => {
      const value = col.getValue
        ? col.getValue(startup)
        : (startup as any)[col.key];

      // escape commas and quotes
      const escaped = String(value ?? "")
        .replace(/"/g, '""');

      return `"${escaped}"`;
    }).join(",")
  );

  const csvContent = [headers, ...rows].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });

  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = "partner_startups_filtered.csv";

  document.body.appendChild(link);
  link.click();

  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const filteredStartups = startups.filter((s) => {

    const q = query.trim().toLowerCase();
    const matchesSearch =
      !q ||
      (s.name && s.name.toLowerCase().includes(q)) ||
      (s.track && s.track.toLowerCase().includes(q)) ||
      (s.company_city && String(s.company_city).toLowerCase().includes(q)) ||
      (s.description &&
        String(s.description).toLowerCase().includes(q)) ||
      (s.deal_synopsis &&
        String(s.deal_synopsis).toLowerCase().includes(q));

    const matchesKeyword =
      keywordTags.length === 0 ||
      keywordTags.every((kw) => {
        const fields = [
          s.keywords,
          s.primary_industry_sector,
          s.all_industries,
          s.verticals,
          s.primary_industry_group,
          s.emerging_spaces,
        ];
        return fields.some(
          (f) => f && String(f).toLowerCase().includes(kw)
        );
      });

    let matchesFilters = true;

    if (
      filters.Industry &&
      (!s.track ||
        s.track.toLowerCase() !== String(filters.Industry).toLowerCase())
    ) {
      matchesFilters = false;
    }

    if (
      filters.Stage &&
      (!s.stage ||
        s.stage.toLowerCase() !== String(filters.Stage).toLowerCase())
    ) {
      matchesFilters = false;
    }

    if (
      filters.Country &&
      (!s.country ||
        s.country.toLowerCase() !== String(filters.Country).toLowerCase())
    ) {
      matchesFilters = false;
    }

    if (
      filters.Continent &&
      (!s.continent ||
        s.continent.toLowerCase() !== String(filters.Continent).toLowerCase())
    ) {
      matchesFilters = false;
    }

    if (filters.Year) {
      const foundedYear = s.founded ? String(s.founded) : "";
      if (foundedYear !== String(filters.Year)) matchesFilters = false;
    }

    if (filters["Total Raised"]) {
      // raised_to_date is stored in millions of USD (e.g. 5.2 = $5.2M)
      const raised = s.raised_to_date != null ? Number(s.raised_to_date) : null;
      if (raised === null || isNaN(raised)) {
        matchesFilters = false;
      } else {
        if (filters["Total Raised"] === "low" && raised > 1) matchesFilters = false;
        if (filters["Total Raised"] === "mid" && (raised <= 1 || raised > 10)) matchesFilters = false;
        if (filters["Total Raised"] === "high" && raised <= 10) matchesFilters = false;
      }
    }

    if (filters.MinEmployees) {
      // Only apply filter if minEmployees is a valid number
      if (s.minEmployees == null) {
        matchesFilters = false;
      } else {
        const minEmp = s.minEmployees;
        if (filters.MinEmployees === "small" && (minEmp < 1 || minEmp > 10)) {
          matchesFilters = false;
        }
        if (
          filters.MinEmployees === "medium" &&
          (minEmp < 11 || minEmp > 50)
        ) {
          matchesFilters = false;
        }
        if (filters.MinEmployees === "large" && minEmp <= 50) {
          matchesFilters = false;
        }
      }
    }

    // GCED filters
    if (filters["Team Decision"]) {
      const decision = (s.gced_team_decision || "").toLowerCase();
      if (decision !== String(filters["Team Decision"]).toLowerCase()) {
        matchesFilters = false;
      }
    }

    if (filters["GCED Track"]) {
      const track = (s.gced_track || "").toLowerCase();
      if (track !== String(filters["GCED Track"]).toLowerCase()) {
        matchesFilters = false;
      }
    }

    if (filters["Average Score"]) {
      const s1 = s.gced_score_1 != null ? Number(s.gced_score_1) : null;
      const s2 = s.gced_score_2 != null ? Number(s.gced_score_2) : null;
      const score =
        s1 != null && s2 != null
          ? (s1 + s2) / 2
          : s1 ?? s2 ?? null;
      if (score == null || Number.isNaN(score)) {
        matchesFilters = false;
      } else {
        if (filters["Average Score"] === "low" && score > 3) matchesFilters = false;
        if (filters["Average Score"] === "medium" && (score <= 3 || score >= 4)) matchesFilters = false;
        if (filters["Average Score"] === "high" && score < 4) matchesFilters = false;
      }
    }

    if (filters["Startup Source"]) {
      const source = (s.gced_startup_source || "").toLowerCase();
      if (source !== String(filters["Startup Source"]).toLowerCase()) {
        matchesFilters = false;
      }
    }

    if (filters["PitchBook Data"]) {
      const hasPB = s.has_pitchbook_data;
      if (filters["PitchBook Data"] === "yes" && !hasPB) matchesFilters = false;
      if (filters["PitchBook Data"] === "no" && hasPB) matchesFilters = false;
    }

    if (filters["GCED Cycle"]) {
      const cycle = (s.gced_cycle || "").toLowerCase();
      if (cycle !== String(filters["GCED Cycle"]).toLowerCase()) {
        matchesFilters = false;
      }
    }

    if (filters["GCED Cycle Year"]) {
      const year = s.gced_cycle_year;
      if (year == null || String(year) !== String(filters["GCED Cycle Year"])) {
        matchesFilters = false;
      }
    }


    if (filters.RevenueRange) {
      const rev = s.revenue != null ? Number(s.revenue) : null;
      if (rev === null || isNaN(rev)) {
        matchesFilters = false;
      } else {
        if (filters.RevenueRange === 'low' && rev > 1) matchesFilters = false;
        if (filters.RevenueRange === 'mid' && (rev <= 1 || rev > 10)) matchesFilters = false;
        if (filters.RevenueRange === 'mid-high' && (rev <= 10 || rev > 100)) matchesFilters = false;
        if (filters.RevenueRange === 'high' && rev <= 100) matchesFilters = false;
      }
    }

        return matchesSearch && matchesFilters && matchesKeyword;
  });

return (
  <div className="flex min-h-screen bg-white">
    {/* LEFT: main content */}
    <div className="flex-1 bg-gray-50 flex flex-col h-screen overflow-hidden">
      
      {/* Fixed header with filters */}
      <div className="bg-gray-50 px-4 pt-4 pb-3 border-b border-gray-100 shrink-0">
        
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={exportToCSV}
              className="px-4 py-2 bg-green-600 text-white text-sm rounded-md hover:bg-green-700"
            >
              Export to CSV
            </button>

            <ViewToggle viewMode={viewMode} setViewMode={setViewMode} />
          </div>
        </div>

        <h1 className="text-3xl font-extrabold text-gray-900">
          Partner Startups
        </h1>

        {error && (
          <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            Error loading startups: {error}
          </div>
        )}

        <div className="mt-3">
          <SearchBar
            onSearch={setQuery}
            placeholder="Search Startups"
            ispartnerstartups
          />
        </div>

        <div className="mt-2">
          <KeywordSearch
            keywords={keywordTags}
            onKeywordsChange={setKeywordTags}
            placeholder="Filter by keyword — type and press Enter (e.g. AI, SaaS, Climate)"
          />
        </div>

        <div className="mt-3 max-w-full overflow-x-auto">
          <FilterBar
            filters={filters}
            setFilters={setFilters}
            startups={startups}
          />
        </div>

      </div>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-hidden px-4 pt-4 pb-8">
        <MainView
          viewMode={viewMode}
          startups={filteredStartups}
          isLoading={isLoading}
          onSelect={(s: StartupDisplay) => setSelectedStartup(s)}
        />
      </div>
    </div>

    {/* RIGHT: details sidebar */}
    <StartupDetailPanel
      startup={selectedStartup}
      onClose={() => setSelectedStartup(null)}
    />
  </div>
);
}


function ViewToggle({
  viewMode,
  setViewMode,
}: {
  viewMode: "cards" | "table";
  setViewMode: React.Dispatch<React.SetStateAction<"cards" | "table">>;
}) {
  return (
    <div className="inline-flex bg-gray-100 rounded-lg p-1">
      <button
        onClick={() => setViewMode("cards")}
        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
          viewMode === "cards"
            ? "bg-white text-gray-900 shadow-sm"
            : "text-gray-600 hover:text-gray-900"
        }`}
        aria-pressed={viewMode === "cards"}
      >
        Cards
      </button>
      <button
        onClick={() => setViewMode("table")}
        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
          viewMode === "table"
            ? "bg-white text-gray-900 shadow-sm"
            : "text-gray-600 hover:text-gray-900"
        }`}
        aria-pressed={viewMode === "table"}
      >
        Table
      </button>
    </div>
  );
}

const statusBadgeKeys = new Set([
  "deal_size_status",
  "financing_status",
  "current_financing_status",
  "current_business_status",
  "deal_class",
  "vc_round",
  "series",
]);

const linkKeys = new Set([
  "company_website",
  "investors_websites",
  "view_company_online",
]);

const emailKeys = new Set(["ceo_email"]);

function normalizeUrl(v: string) {
  if (!v) return "";
  if (v.startsWith("http://") || v.startsWith("https://")) return v;
  return `https://${v}`;
}

// const sortStartups = (startups: StartupDisplay[]): StartupDisplay[] => {
//   return [...startups].sort((a, b) => {
//     const aHasProject = !!(a.gced_track && a.gced_track.trim());
//     const bHasProject = !!(b.gced_track && b.gced_track.trim());

//     // Active project first
//     if (aHasProject !== bHasProject) return aHasProject ? -1 : 1;

//     // Then alphabetical by company name
//     return (a.name || "").localeCompare(b.name || "", undefined, {
//       sensitivity: "base",
//     });
//   });
// };

const sortStartups = (startups: StartupDisplay[]): StartupDisplay[] => {
  const hasProject = (s: StartupDisplay) => s.associatedProjectName !== "N/A";

  return [...startups].sort((a, b) => {
    const aHas = hasProject(a);
    const bHas = hasProject(b);

    // 1) Startups with a project first
    if (aHas !== bHas) return aHas ? -1 : 1;

    // 2) Both have a project → sort by year desc; no year goes after those with a year
    if (aHas && bHas) {
      const ay = a.gced_cycle_year ?? null;
      const by_ = b.gced_cycle_year ?? null;
      if (ay !== null && by_ !== null && ay !== by_) return by_ - ay;
      if (ay !== null && by_ === null) return -1;
      if (ay === null && by_ !== null) return 1;
    }

    // 3) No project → alphabetical A–Z
    return (a.name || "").localeCompare(b.name || "", undefined, {
      sensitivity: "base",
    });
  });
};

function MainView({
  viewMode,
  startups,
  isLoading,
  onSelect,
}: {
  viewMode: "cards" | "table";
  startups: StartupDisplay[];
  isLoading: boolean;
  onSelect: (s: StartupDisplay) => void;
}) {
  if (isLoading) {
    return (
      <div className="text-center text-gray-500 py-12">
        Loading partner startups…
      </div>
    );
  }

  if (!startups || startups.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-gray-500">
        No startups match your filters.
      </div>
    );
  }

  if (viewMode === "cards") {
    return (
      <div className="h-full overflow-y-auto">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {sortStartups(startups).map((startup) => (
            <StartupCard
              key={startup.id}
              startup={{
                id: Number(startup.id) || 0,
                name: startup.name,
                employees: startup.minEmployees ?? null,
                status: startup.status,
                stage: startup.stageLevel || startup.stage || null,
                industry: startup.track,
                associatedProject: startup.associatedProjectName,
                summary: startup.shortDesc,
                profilePics: startup.profilePics,
                hasGCEDMatch: startup.has_gced_match,
                gcedTeamDecision: startup.gced_team_decision,
              }}
              onClick={() => onSelect(startup)}
            />
          ))}
        </div>
      </div>
    );
  }

  const renderCell = (key: string, raw: any) => {
    if (raw === null || raw === undefined || raw === "") return "—";

    if (typeof raw === "boolean") {
      return (
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
            raw ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"
          }`}
        >
          {raw ? "Yes" : "No"}
        </span>
      );
    }

    let value = raw;

    if (Array.isArray(value)) value = value.join(", ");
    else if (typeof value === "object") value = JSON.stringify(value);

    const v = String(value);

    if (emailKeys.has(key)) {
      return (
        <a
          href={`mailto:${v}`}
          className="text-blue-600 hover:underline"
          title={v}
        >
          {v}
        </a>
      );
    }

    if (linkKeys.has(key)) {
      const url = normalizeUrl(v);
      return (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-blue-600 hover:underline"
          title={v}
        >
          {v}
        </a>
      );
    }

    if (statusBadgeKeys.has(key)) {
      return (
        <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800">
          {v}
        </span>
      );
    }

    return (
      <span className="block max-w-[260px] truncate" title={v}>
        {v}
      </span>
    );
  };

  const cols = PARTNER_STARTUP_COLUMNS;

  return (
    <div className="partner-startups-table h-full overflow-y-auto overflow-x-scroll bg-white rounded-xl shadow border border-gray-200">
        <table className="text-sm border-collapse min-w-full">
          <thead className="sticky top-0 z-20">
            <tr className="bg-(--color-custom-red)">
              {cols.map((c, i) => (
                <th
                  key={c.key}
                  className={`px-4 py-3 text-left text-[11px] font-bold text-white uppercase tracking-wider whitespace-nowrap bg-(--color-custom-red) sticky top-0 ${i === 0 ? "left-0 z-30 border-r border-white/20" : "z-20"}`}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortStartups(startups).map((s, rowIdx) => (
              <tr
                key={s.id}
                className="group border-b cursor-pointer"
                onClick={() => onSelect(s)}
              >
                {cols.map((c, i) => (
                  <td
                    key={c.key}
                    className={[
                      "px-4 py-2.5 align-top transition-colors group-hover:bg-rose-100",
                      rowIdx % 2 === 1 ? "bg-gray-50" : "bg-white",
                      i === 0
                        ? "sticky left-0 z-10 w-44 max-w-[176px] font-semibold text-[#8B1E2F] border-r border-gray-100 shadow-[2px_0_4px_-2px_rgba(0,0,0,0.06)]"
                        : "text-gray-700",
                    ].join(" ")}
                  >
                    {renderCell(c.key, c.getValue ? c.getValue(s) : (s as any)[c.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
    </div>
  );
}
