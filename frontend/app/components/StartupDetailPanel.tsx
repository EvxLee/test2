import React from "react";
import { PARTNER_STARTUP_COLUMNS } from "app/lib/partnerStartupColumns";
import type { PartnerStartupColumn } from "app/lib/partnerStartupColumns";

function normalizeUrl(v: string) {
  if (!v) return "";
  if (v.startsWith("http://") || v.startsWith("https://")) return v;
  return `https://${v}`;
}

function renderValue(key: string, raw: any) {
  if (raw === null || raw === undefined || raw === "" || raw === "—") {
    return <span className="text-gray-400 italic">—</span>;
  }
  if (typeof raw === "boolean") {
    return (
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
          raw ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"
        }`}
      >
        {raw ? "Yes" : "No"}
      </span>
    );
  }

  const v = Array.isArray(raw) ? raw.join(", ") : String(raw);

  if (key === "company_website" || key === "linkedin_url") {
    const url = normalizeUrl(v);
    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="text-blue-600 hover:underline break-all font-medium"
      >
        {v}
      </a>
    );
  }
  if (key === "primary_contact_email") {
    return (
      <a href={`mailto:${v}`} className="text-blue-600 hover:underline break-all font-medium">
        {v}
      </a>
    );
  }

  return <span className="text-gray-800 break-words">{v}</span>;
}

const Field = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div className="flex flex-col gap-0.5 min-w-0">
    <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 leading-none">
      {label}
    </span>
    <div className="text-sm mt-0.5">{value}</div>
  </div>
);

// PitchBook columns organized into visual sub-groups
const PB_GROUPS: {
  label: string;
  headerColor: string;
  cardColor: string;
  keys: string[];
}[] = [
  {
    label: "Contact & Web",
    headerColor: "text-sky-700",
    cardColor: "bg-sky-50 border-sky-200",
    keys: [
      "company_website",
      "primary_contact",
      "primary_contact_title",
      "primary_contact_email",
      "primary_contact_phone",
      "linkedin_url",
    ],
  },
  {
    label: "Industry",
    headerColor: "text-violet-700",
    cardColor: "bg-violet-50 border-violet-200",
    keys: [
      "primary_industry_sector",
      "primary_industry_group",
      "verticals",
      "keywords",
      "description",
    ],
  },
  {
    label: "Financials",
    headerColor: "text-amber-700",
    cardColor: "bg-amber-50 border-amber-200",
    keys: [
      "revenue",
      "raised_to_date",
      "first_financing_deal_type_1",
      "first_financing_deal_class",
      "last_financing_date",
      "last_financing_size",
      "last_financing_deal_type_1",
      "last_financing_deal_class",
    ],
  },
  {
    label: "Investors",
    headerColor: "text-teal-700",
    cardColor: "bg-teal-50 border-teal-200",
    keys: ["investors"],
  },
  {
    label: "Location",
    headerColor: "text-orange-700",
    cardColor: "bg-orange-50 border-orange-200",
    keys: [
      "company_city",
      "company_state_province",
      "company_country_region",
      "hq_global_region",
    ],
  },
  {
    label: "Company Info",
    headerColor: "text-slate-600",
    cardColor: "bg-slate-50 border-slate-200",
    keys: [
      "company_legal_name",
      "competitors",
      "current_employees",
      "employee_history",
      "year_founded",
      "opportunity_score",
      "last_updated_date",
    ],
  },
];

// Fields that should span both grid columns (long text values)
const FULL_WIDTH_KEYS = new Set([
  "description",
  "competitors",
  "employee_history",
  "investors",
]);

export default function StartupDetailPanel({
  startup,
  onClose,
}: {
  startup: any;
  onClose: () => void;
}) {
  if (!startup) return null;

  const mondayCols = PARTNER_STARTUP_COLUMNS.filter((c) => c.group === "Monday.com");
  const pbColMap = new Map(
    PARTNER_STARTUP_COLUMNS.filter((c) => c.group === "PitchBook").map((c) => [c.key, c])
  );

  return (
    <aside
      className="fixed right-0 top-0 z-40 h-screen w-[460px] max-w-full bg-white border-l border-gray-200 shadow-2xl flex flex-col"
      role="dialog"
      aria-modal="true"
    >
      {/* Brand accent bar */}
      <div className="h-1 w-full bg-[#8B1E2F] shrink-0" />

      {/* Header */}
      <div className="px-5 pt-4 pb-4 border-b border-gray-100 shrink-0">
        <div className="flex justify-between items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-bold text-gray-900 leading-tight">
              {startup.startups || startup.name || "Startup"}
            </h2>
            <p className="text-xs mt-1.5 line-clamp-3 leading-relaxed text-gray-500">
              {startup.deal_synopsis || startup.description || (
                <span className="italic text-gray-400">No description available.</span>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-gray-100 hover:bg-gray-200 text-gray-500 hover:text-gray-800 transition-colors text-xl leading-none font-light"
            aria-label="Close"
          >
            ×
          </button>
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">

        {/* Monday.com section */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-xs font-semibold text-emerald-800 uppercase tracking-wide">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              Monday.com
            </span>
          </div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              {mondayCols.map((c) => {
                const raw = c.getValue ? c.getValue(startup) : startup[c.key];
                return (
                  <Field key={c.key} label={c.label} value={renderValue(c.key, raw)} />
                );
              })}
            </div>
          </div>
        </section>

        {/* PitchBook section */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 border border-blue-200 px-2.5 py-1 text-xs font-semibold text-blue-800 uppercase tracking-wide">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
              PitchBook
            </span>
          </div>

          <div className="space-y-2.5">
            {PB_GROUPS.map((group) => {
              const cols = group.keys
                .map((k) => pbColMap.get(k))
                .filter(Boolean) as PartnerStartupColumn[];
              if (cols.length === 0) return null;

              return (
                <div key={group.label} className={`rounded-lg border p-3 ${group.cardColor}`}>
                  <p
                    className={`text-[10px] font-bold uppercase tracking-widest mb-2.5 ${group.headerColor}`}
                  >
                    {group.label}
                  </p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    {cols.map((c) => {
                      const raw = c.getValue ? c.getValue(startup) : startup[c.key];
                      return (
                        <div key={c.key} className={FULL_WIDTH_KEYS.has(c.key) ? "col-span-2" : ""}>
                          <Field label={c.label} value={renderValue(c.key, raw)} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </aside>
  );
}
