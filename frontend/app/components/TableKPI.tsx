import React, { useState } from "react";
import type Project from "./../types/Project";
import type { ProjectStatus, ProjectVertical } from "./../types/Project";
import { sortProjects, groupByStatus } from "~/lib/projects";
import { ChevronDown } from "lucide-react";
import WPMSummaryCards from "./WPMSummaryCards";

interface TableKPIProps {
  data: Project[];
}

const statusStyles: Record<ProjectStatus, { text: string }> = {
  Ongoing: { text: "text-green-700" },
  "On Hold": { text: "text-yellow-700" },
  Archived: { text: "text-rose-700" },
};

// AI=blue, Cleantech=green, Healthtech=purple
const verticalStyles: Record<ProjectVertical, { chip: string }> = {
  AI: {
    chip:
      "inline-flex items-center rounded-xl px-2.5 py-0.5 text-sm font-medium bg-blue-100 text-blue-800",
  },
  Cleantech: {
    chip:
      "inline-flex items-center rounded-xl px-2.5 py-0.5 text-sm font-medium bg-green-100 text-green-800",
  },
  Healthtech: {
    chip:
      "inline-flex items-center rounded-xl px-2.5 py-0.5 text-sm font-medium bg-purple-100 text-purple-800",
  },
};

function formatDeadline(d?: string | Date) {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  if (isNaN(date.getTime())) return String(d);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const TABLE_MIN_WIDTH = "min-w-[980px]";

export default function TableKPI({ data }: TableKPIProps) {
  const total = data.length;
  const sorted = [...data].sort(sortProjects);
  const groups = groupByStatus(sorted);

  const [open, setOpen] = useState<Record<ProjectStatus, boolean>>({
    Ongoing: false,
    "On Hold": false,
    Archived: false,
  });

  const toggle = (status: ProjectStatus) =>
    setOpen((s) => ({ ...s, [status]: !s[status] }));

  const Pill = ({ children }: { children: React.ReactNode }) => (
    <span className="inline-flex items-center rounded-xl bg-gray-800/80 text-white px-2.5 py-0.5 text-sm font-medium">
      {children}
    </span>
  );

  const StagePill = ({ stage }: { stage: Project["stage"] }) => (
    <span className="inline-flex items-center rounded-xl bg-slate-100 text-slate-800 px-2.5 py-0.5 text-sm font-semibold">
      {stage ?? "—"}
    </span>
  );

  return (
    <section className="mt-8 rounded-lg overflow-hidden shadow">
      {/* Header bar */}
      <div className="bg-[#7b1c2f] text-white px-6 py-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Ongoing Projects Overview</h2>
          <p className="text-white/80 text-sm">Stage 2-5</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-white/80">Total Projects</p>
          <p className="text-2xl font-bold">{total}</p>
        </div>
      </div>

      {/* Table area */}
      <div className="bg-white overflow-x-auto">
        <div className={TABLE_MIN_WIDTH}>
          {/* Table header */}
          <div className="grid grid-cols-12 gap-x-6 md:gap-x-5 sm:gap-x-3 gap-y-4 px-6 py-3 border-b text-sm font-medium text-gray-600">
            <div className="col-span-3 min-w-0">Project</div>
            <div className="col-span-2 min-w-0">Owner</div>
            <div className="col-span-2 min-w-0">Startup</div>
            <div className="col-span-2 min-w-0">Deadline</div>
            <div className="col-span-1 min-w-0 text-center">Stage</div>
            <div className="col-span-2 min-w-0 text-right">Vertical</div>
          </div>

          {/* Sections (grouped by status) */}
          {(["Ongoing", "On Hold", "Archived"] as ProjectStatus[]).map(
            (status) => {
              const rows = groups[status] ?? [];

              return (
                <div key={status} className="border-b last:border-0">
                  {/* Section header */}
                  <button
                    type="button"
                    onClick={() => toggle(status)}
                    aria-expanded={open[status]}
                    className="w-full px-6 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`text-sm font-semibold ${statusStyles[status].text}`}
                      >
                        {status}
                      </span>
                      <span className="text-xs text-gray-500">
                        • {rows.length}{" "}
                        {rows.length === 1 ? "project" : "projects"}
                      </span>
                    </div>
                    <ChevronDown
                      className={`h-4 w-4 transition-transform ${
                        open[status] ? "rotate-180" : ""
                      }`}
                      aria-hidden="true"
                    />
                  </button>

                  {/* Collapsible content */}
                  <div
                    className={`overflow-hidden transition-[max-height,opacity] duration-300 ${
                      open[status]
                        ? "max-h-[2000px] opacity-100"
                        : "max-h-0 opacity-0"
                    }`}
                  >
                    {rows.length === 0 ? (
                      <div className="px-6 py-6 text-sm text-gray-500">
                        No projects.
                      </div>
                    ) : (
                      rows.map((p) => (
                        <div
                          key={p.id}
                          className="grid grid-cols-12 gap-x-6 md:gap-x-5 sm:gap-x-3 gap-y-2 px-6 py-4 border-t items-center"
                        >
                          {/* Project name */}
                          <div className="col-span-3 min-w-0">
                            <div className="font-semibold text-gray-900 truncate">
                              {p.name}
                            </div>
                          </div>

                          {/* Owner */}
                          <div className="col-span-2 min-w-0 overflow-hidden">
                            <p className="text-sm text-gray-900 truncate">
                              {p.owner}
                            </p>
                          </div>

                          {/* Startup pill */}
                          <div className="col-span-2 min-w-0 overflow-hidden">
                            {p.startupName && p.startupName !== "—" ? (
                              <Pill>
                                <span className="truncate block max-w-[10rem]">
                                  {p.startupName}
                                </span>
                              </Pill>
                            ) : (
                              <span className="text-sm text-gray-900">—</span>
                            )}
                          </div>

                          {/* Deadline */}
                          <div className="col-span-2 min-w-0">
                            <span className="text-sm text-gray-900 truncate">
                              {formatDeadline(p.deadline)}
                            </span>
                          </div>

                          {/* Stage (center) */}
                          <div className="col-span-1 min-w-0 text-center">
                            <StagePill stage={p.stage} />
                          </div>

                          {/* Vertical chip (right align) */}
                          <div className="col-span-2 min-w-0 text-right">
                            <span className={verticalStyles[p.vertical].chip}>
                              {p.vertical}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            }
          )}
        </div>
      </div>
      <WPMSummaryCards data={data} />
    </section>
  );
}
