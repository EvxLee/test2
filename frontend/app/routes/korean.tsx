"use client";

import { useState, useEffect } from "react";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

interface KoreanProject {
  id: string;
  project_id: string;
  project_name: string;
  stage: string;
  vertical: string;
  status: string;
  business_theme: string;
  timeline: string;
  main_customer: string;
  monthly_activities: string;
}

const KOREAN_COLUMNS = [
  "project_name",
  "stage",
  "vertical",
  "status",
  "business_theme",
  "timeline",
  "main_customer",
  "monthly_activities",
];

const COLUMN_PRETTY: Record<string, string> = {
  project_name: "Project Name",
  stage: "Stage",
  vertical: "Vertical",
  status: "Status",
  business_theme: "Business Theme",
  timeline: "Timeline",
  main_customer: "Main Customer",
  monthly_activities: "Monthly Activities",
};

export default function Korean() {
  const [projects, setProjects] = useState<KoreanProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<KoreanProject | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchKoreanData() {
      try {
        setIsLoading(true);
        setError(null);

        const columns = [
          "id",
          "project_id",
          "project_name",
          "stage",
          "vertical",
          "status",
          "business_theme",
          "timeline",
          "main_customer",
          "monthly_activities",
        ].join(",");

        const url = `${BASE_URL}/atlas/display/data?schema=master_dashboard&table=korean&columns=${columns}&limit=500`;

        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${API_TOKEN}`,
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch regional data: ${response.status}`);
        }

        const data = await response.json();
        setProjects(data.rows || []);
      } catch (err: any) {
        setError(err?.message || "An unexpected error occurred.");
      } finally {
        setIsLoading(false);
      }
    }

    fetchKoreanData();
  }, []);

  return (
    <div className="flex h-screen bg-white">
      <div className="flex-1 p-4 overflow-y-auto bg-gray-50">
        <h1 className="text-3xl font-extrabold text-gray-900 text-center mb-6">
          Regional Projects
        </h1>

        {isLoading && (
          <div className="text-center text-gray-600">Loading...</div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 max-w-2xl mx-auto">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {!isLoading && !error && (
          <TableView projects={projects} onSelect={setSelectedProject} />
        )}
      </div>

      {selectedProject && (
        <aside className="fixed right-0 top-0 z-40 h-screen w-[420px] max-w-full bg-white border-l border-gray-100 shadow-xl p-6 overflow-y-auto transition-transform duration-300">
          <div className="flex justify-between items-start">
            <div className="pr-4">
              <h2 className="text-2xl font-semibold text-gray-900">
                {selectedProject.project_name}
              </h2>
              <p className="text-sm text-gray-600 mt-1">{selectedProject.business_theme}</p>
            </div>
            <div className="ml-2 shrink-0">
              <button
                onClick={() => setSelectedProject(null)}
                className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-3 py-1 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>

          <hr className="my-4 border-gray-100" />

          <div className="space-y-3 text-sm pb-6">
            {KOREAN_COLUMNS.map((col) => (
              <Info key={col} label={COLUMN_PRETTY[col]} value={(selectedProject as any)[col]} />
            ))}
          </div>
        </aside>
      )}
    </div>
  );
}

function TableView({ projects, onSelect }: { projects: KoreanProject[]; onSelect: (p: KoreanProject) => void }) {
  const [sortKey, setSortKey] = useState<string>("project_name");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  const sortedProjects = [...projects].sort((a, b) => {
    const aVal = (a as any)[sortKey];
    const bVal = (b as any)[sortKey];

    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return sortDirection === "asc" ? 1 : -1;
    if (bVal == null) return sortDirection === "asc" ? -1 : 1;

    if (typeof aVal === "number" && typeof bVal === "number") {
      return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
    }

    const aStr = String(aVal).toLowerCase();
    const bStr = String(bVal).toLowerCase();
    if (aStr < bStr) return sortDirection === "asc" ? -1 : 1;
    if (aStr > bStr) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  if (!projects || projects.length === 0) {
    return <div className="text-center text-gray-600">No projects to display.</div>;
  }

  return (
    <div className="overflow-x-auto bg-white rounded-md shadow">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            {KOREAN_COLUMNS.map((col) => (
              <th
                key={col}
                className="px-3 py-2 text-left text-xs font-medium text-gray-600 border-b cursor-pointer hover:bg-gray-100 select-none"
                onClick={() => handleSort(col)}
              >
                <div className="flex items-center gap-1">
                  {COLUMN_PRETTY[col]}
                  {sortKey === col && (
                    <span className="text-gray-400">
                      {sortDirection === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedProjects.map((p) => (
            <tr
              key={p.id || p.project_id}
              className="hover:bg-gray-50 border-b cursor-pointer"
              onClick={() => onSelect(p)}
            >
              {KOREAN_COLUMNS.map((col) => {
                let value = (p as any)[col];
                if (Array.isArray(value)) value = value.join(", ");
                else if (value && typeof value === "object") value = JSON.stringify(value);
                else if (value === null || value === undefined) value = "—";
                return (
                  <td key={col} className="px-3 py-2 align-top text-gray-700">
                    <div className="max-w-[280px] truncate">{String(value)}</div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Info({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex flex-col">
      <span className="font-semibold text-gray-900">{label}:</span>
      <span className="text-gray-600 break-words">{value || "—"}</span>
    </div>
  );
}
