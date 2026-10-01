import { useEffect, useState } from "react";
import Header from "../components/Header";
import TableKPI from "~/components/TableKPI";
import GCEDDashboard from "../components/GCEDSummaryTable";
import CycleSummaryPanel from "../components/CycleSummaryPanel";
import type Project from "~/types/Project";
import type { ProjectStatus, ProjectVertical } from "~/types/Project";
import { useBoardConfig } from "app/lib/useBoardConfig";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

interface ProjectRow {
  id: string;
  name: string;
  company_name: string | null;
  stage_name: string | null;
  atlas_project_stage: string | null;
  project_stage: string | null;
  status_category: string | null;
  project_status: string | null;
  is_ongoing: boolean | null;
  vertical_id: string | null;
  owner_id: string | null;
  tech_lead: string | null;
  description: string | null;
}

interface VerticalRow {
  id: string;
  vertical_name: string;
}

interface PersonRow {
  id: string;
  full_name: string;
}

interface PartnerStartupRow {
  project_id: string;
  startup_name: string;
}

function parseStageNumber(stageName: string | null): 2 | 3 | 4 | 5 | null {
  if (!stageName) return null;
  const match = stageName.match(/(\d)/);
  if (match) {
    const num = parseInt(match[1], 10);
    if (num >= 2 && num <= 5) return num as 2 | 3 | 4 | 5;
  }
  return null;
}

export default function Dashboard() {
  const { projectBoardFilter } = useBoardConfig();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCycle, setSelectedCycle] = useState<{ key: string; label: string } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setIsLoading(true);

        const baseUrl = `${BASE_URL}/atlas/display/data?schema=master_dashboard&redact=off`;
        const projectBoardFilterParam = `&filter=${encodeURIComponent(projectBoardFilter)}`;
        const authHeader = {
          Authorization: `Bearer ${API_TOKEN}`,
        };

        const [projectsRes, verticalsRes, peopleRes, partnerStartupsRes] = await Promise.all([
          fetch(
            `${baseUrl}&table=projects&limit=500${projectBoardFilterParam}&columns=` +
              [
                "id",
                "name",
                "company_name",
                "stage_name",
                "atlas_project_stage",
                "project_stage",
                "status_category",
                "project_status",
                "is_ongoing",
                "vertical_id",
                "owner_id",
                "tech_lead",
                "description",
              ].join(","),
            { headers: authHeader }
          ),
          fetch(`${baseUrl}&table=verticals&columns=id,vertical_name`, {
            headers: authHeader,
          }),
          fetch(`${baseUrl}&table=people&columns=id,full_name`, {
            headers: authHeader,
          }),
          fetch(
            `${baseUrl}&table=project_partner_startups&limit=500&columns=project_id,startup_name`,
            { headers: authHeader }
          ),
        ]);

        if (!projectsRes.ok) {
          throw new Error("Failed to load projects");
        }

        const projectsJson = await projectsRes.json();
        const verticalsJson = await verticalsRes.json();
        const peopleJson = await peopleRes.json();
        const partnerStartupsJson = partnerStartupsRes.ok ? await partnerStartupsRes.json() : { rows: [] };

        const projectsData: ProjectRow[] = projectsJson.rows || [];
        const verticalsData: VerticalRow[] = verticalsJson.rows || [];
        const peopleData: PersonRow[] = peopleJson.rows || [];
        const partnerStartupsData: PartnerStartupRow[] = partnerStartupsJson.rows || [];

        // project_id → unique startup names
        const partnerStartupMap: Record<string, string[]> = {};
        partnerStartupsData.forEach((row) => {
          if (!partnerStartupMap[row.project_id]) partnerStartupMap[row.project_id] = [];
          if (!partnerStartupMap[row.project_id].includes(row.startup_name)) {
            partnerStartupMap[row.project_id].push(row.startup_name);
          }
        });

        // Build lookup maps
        const verticalMap: Record<string, string> = {};
        verticalsData.forEach((v) => {
          verticalMap[v.id] = v.vertical_name;
        });

        const peopleMap: Record<string, string> = {};
        peopleData.forEach((person) => {
          peopleMap[person.id] = person.full_name;
        });

        // Map API response to Project interface
        const mapped: Project[] = projectsData.map((p) => {
          const verticalName = p.vertical_id ? verticalMap[p.vertical_id] : null;
          let vertical: ProjectVertical = "AI";
          if (verticalName) {
            if (/health/i.test(verticalName)) {
              vertical = "Healthtech";
            } else if (/clean/i.test(verticalName)) {
              vertical = "Cleantech";
            }
          }

          // Match same priority as projects.tsx
          const rawStatus = p.status_category || p.project_status || "";
          let statusCategory: ProjectStatus = "Ongoing";
          if (/hold/i.test(rawStatus)) {
            statusCategory = "On Hold";
          } else if (/archiv/i.test(rawStatus)) {
            statusCategory = "Archived";
          } else if (p.is_ongoing === false) {
            statusCategory = "Archived";
          }

          // Stage label — same priority as projects.tsx
          const stageLabel =
            p.atlas_project_stage ||
            p.project_stage ||
            p.stage_name ||
            "";

          const owner =
            p.tech_lead ||
            (p.owner_id ? peopleMap[p.owner_id] || "—" : "—");

          return {
            id: p.id,
            name: p.name || "—",
            description: p.description || "",
            startupName: partnerStartupMap[p.id]?.length
              ? partnerStartupMap[p.id].join(", ")
              : "—",
            stage: parseStageNumber(stageLabel),
            status: stageLabel || "—",
            statusCategory,
            vertical,
            deadline: undefined,
            owner,
            stagesCompletedCY: [],
          };
        });

        // Filter: include archived projects, and ongoing/on-hold only if stage 2-5
        const filteredByStage = mapped.filter((p) => {
          if (p.statusCategory === "Archived") return true;

          const stageMatch = p.status.match(/Stage (\d+)/i);
          if (!stageMatch) return false;
          const stageNum = parseInt(stageMatch[1], 10);
          return stageNum >= 2 && stageNum <= 5;
        });

        setProjects(filteredByStage);
      } catch (err) {
        console.error("Error loading dashboard data:", err);
      } finally {
        setIsLoading(false);
      }
    }

    load();
  }, [projectBoardFilter]);

  return (
    <div className="max-w-5xl mx-auto mt-10 p-6 space-y-6">
      <div className="rounded-lg overflow-hidden shadow">
        <Header
          title="Startup Sourcing Overview"
          subtitle="Combined totals across all GCED cycles"
        />
        <GCEDDashboard
          onCycleClick={(key, label) => setSelectedCycle({ key, label })}
        />
      </div>
      {isLoading ? (
        <div className="p-10 text-center text-gray-500">Loading projects...</div>
      ) : (
        <TableKPI data={projects} />
      )}

      {selectedCycle && (
        <CycleSummaryPanel
          cycleKey={selectedCycle.key}
          cycleLabel={selectedCycle.label}
          onClose={() => setSelectedCycle(null)}
        />
      )}
    </div>
  );
}
