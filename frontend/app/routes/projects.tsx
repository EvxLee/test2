import React, { useEffect, useState } from "react";
import SearchBar from "app/components/Searchbar";
import ProjectFilterBar from "./projects/components/ProjectFilterBar";
import ProjectCard from "./projects/components/ProjectCard";
import ProjectStartupsPanel from "./projects/components/ProjectStartupsPanel";
import { useBoardConfig } from "app/lib/useBoardConfig";
import type Project from "app/types/Project";
import type { ProjectStatus, ProjectVertical } from "app/types/Project";
import { useChatContext } from "../contexts/ChatContext";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

// Matches master_dashboard.projects
interface ProjectRow {
  id: string;
  name: string | null;
  company_name: string | null;
  description: string | null;
  cycle_name: string | null;
  vertical_id: string | null;
  project_stage: string | null;
  atlas_project_stage: string | null;
  project_status: string | null;
  status_category: string | null;
  tech_lead: string | null;
  stage_name: string | null;
  owner_id: string | null;
  is_ongoing: boolean | null;
  source_item_id: string | null;
}

// Raw Monday column value row from monday.item_properties
interface MondayItemPropRow {
  monday_item_id: string;
  value_text: string | null;
  raw_json: { title?: string; [key: string]: unknown } | null;
}

interface VerticalRow {
  id: string;
  vertical_name: string;
}

interface PersonRow {
  id: string;
  full_name: string;
}

interface ProjectStageRow {
  id: string;
  project_id: string;
  stage_type_id: string;
  sequence_no: number;
}

interface StageTypeRow {
  id: string;
  stage_name: string;
}

interface PartnerStartupRow {
  project_id: string;
  startup_name: string;
  stage: string | null;
}

interface ContractRow {
  id: string;
  contract: string;
  contract_amount: number | null;
  detail_scope: string | null;
  status_label: string | null;
  project_id?: string | null;
  stage?: string | null;
  project_stage_id?: string | null;
}

interface BudgetByStageRow {
  project_id: string;
  project_name: string;
  stage_id: string;
  stage_name: string;
  total_amount: number;
}

type ExtendedProject = Project & {
  statusCategory: ProjectStatus;
  totalExpenditure: number;
};

export default function Projects() {
  const { projectBoardFilter } = useBoardConfig();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<any>({});
  const [projects, setProjects] = useState<ExtendedProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<ExtendedProject | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [contracts, setContracts] = useState<ContractRow[]>([]);
  const [budgetByStage, setBudgetByStage] = useState<BudgetByStageRow[] | null>(null);
  const [collapsedStages, setCollapsedStages] = useState<Set<string>>(new Set());
  // Maps projects.id → the project_id used in contract_status (may differ after schema change)
  const [contractProjectIdMap, setContractProjectIdMap] = useState<Record<string, string>>({});
  const [partnerStartupsByProject, setPartnerStartupsByProject] = useState<Record<string, { stage: string | null; startup_name: string }[]>>({});

  const { setContext } = useChatContext();

  useEffect(() => {
    async function load() {
      try {
        setIsLoading(true);

        const baseUrl = `${BASE_URL}/atlas/display/data?schema=master_dashboard&redact=off`;
        const projectBoardFilterParam = `&filter=${encodeURIComponent(projectBoardFilter)}`;
        const authHeader = {
          Authorization: `Bearer ${API_TOKEN}`,
        };

        const [projectsRes, contractsRes, peopleRes, projectStagesRes, stageTypesRes, verticalsRes, globalBudgetRes, partnerStartupsRes] =
          await Promise.all([
            fetch(
              `${baseUrl}&table=projects&limit=500${projectBoardFilterParam}&columns=` +
                [
                  "id",
                  "name",
                  "company_name",
                  "description",
                  "cycle_name",
                  "vertical_id",
                  "project_stage",
                  "atlas_project_stage",
                  "project_status",
                  "status_category",
                  "tech_lead",
                  "stage_name",
                  "owner_id",
                  "is_ongoing",
                  "source_item_id",
                ].join(","),
              { headers: authHeader }
            ),
            fetch(
              `${baseUrl}&table=contract_status&limit=500&columns=id,contract,contract_amount,detail_scope,status_label,project_id,stage,project_stage_id`,
              { headers: authHeader }
            ),
            fetch(`${baseUrl}&table=people&limit=500&columns=id,full_name`, {
              headers: authHeader,
            }),
            fetch(
              `${baseUrl}&table=project_stages&limit=2000&columns=id,project_id,stage_type_id,sequence_no`,
              { headers: authHeader }
            ),
            fetch(
              `${baseUrl}&table=stage_types&limit=100&columns=id,stage_name`,
              { headers: authHeader }
            ),
            fetch(`${baseUrl}&table=verticals&limit=100&columns=id,vertical_name`, {
              headers: authHeader,
            }),
            // Global budget-by-stage: project_id here matches contract_status.project_id
            fetch(`${BASE_URL}/atlas/display/budget-by-stage`, { headers: authHeader }),
            fetch(
              `${baseUrl}&table=project_partner_startups&limit=500&columns=project_id,startup_name,stage`,
              { headers: authHeader }
            ),
          ]);

        if (!projectsRes.ok) {
          throw new Error("Failed to load projects");
        }

        const projectsJson = await projectsRes.json();
        const contractsJson = await contractsRes.json();
        const peopleJson = peopleRes.ok ? await peopleRes.json() : { rows: [] };
        const projectStagesJson = projectStagesRes.ok ? await projectStagesRes.json() : { rows: [] };
        const stageTypesJson = stageTypesRes.ok ? await stageTypesRes.json() : { rows: [] };
        const verticalsJson = verticalsRes.ok ? await verticalsRes.json() : { rows: [] };
        const globalBudgetJson = globalBudgetRes.ok ? await globalBudgetRes.json() : [];
        const partnerStartupsJson = partnerStartupsRes.ok ? await partnerStartupsRes.json() : { rows: [] };

        const projectsData: ProjectRow[] = projectsJson.rows || [];
        const contractsData: ContractRow[] = contractsJson.rows || [];

        // Global budget rows: project_id here is what contract_status.project_id references
        const globalBudgetRows: BudgetByStageRow[] = Array.isArray(globalBudgetJson)
          ? globalBudgetJson
          : (globalBudgetJson.rows || []);

        // Build name → budget project_id map (case-insensitive)
        const budgetIdByName: Record<string, string> = {};
        globalBudgetRows.forEach((row) => {
          if (row.project_name && row.project_id) {
            budgetIdByName[row.project_name.toLowerCase().trim()] = row.project_id;
          }
        });

        // Build projects.id → contract_status project_id via name match
        const idMap: Record<string, string> = {};
        projectsData.forEach((p) => {
          const key = (p.name || "").toLowerCase().trim();
          const budgetId = budgetIdByName[key];
          if (budgetId) idMap[p.id] = budgetId;
        });
        setContractProjectIdMap(idMap);
        const peopleData: PersonRow[] = peopleJson.rows || [];
        const projectStagesData: ProjectStageRow[] = projectStagesJson.rows || [];
        const stageTypesData: StageTypeRow[] = stageTypesJson.rows || [];
        const verticalsData: VerticalRow[] = verticalsJson.rows || [];
        const partnerStartupsData: PartnerStartupRow[] = partnerStartupsJson.rows || [];

        // project_id → unique startup entries (with stage)
        const partnerStartupMap: Record<string, string[]> = {};
        const structuredStartupMap: Record<string, { stage: string | null; startup_name: string }[]> = {};
        partnerStartupsData.forEach((row) => {
          if (!partnerStartupMap[row.project_id]) partnerStartupMap[row.project_id] = [];
          if (!partnerStartupMap[row.project_id].includes(row.startup_name)) {
            partnerStartupMap[row.project_id].push(row.startup_name);
          }
          if (!structuredStartupMap[row.project_id]) structuredStartupMap[row.project_id] = [];
          structuredStartupMap[row.project_id].push({ stage: row.stage, startup_name: row.startup_name });
        });
        setPartnerStartupsByProject(structuredStartupMap);

        const peopleMap: Record<string, string> = {};
        peopleData.forEach((p) => { peopleMap[p.id] = p.full_name; });

        // stage_type_id → stage_name
        const stageTypeMap: Record<string, string> = {};
        stageTypesData.forEach((st) => { stageTypeMap[st.id] = st.stage_name; });

        // project_id → stage_name of the highest-sequence stage
        const projectCurrentStage: Record<string, string> = {};
        const projectStageSeq: Record<string, number> = {};
        projectStagesData.forEach((ps) => {
          const stageName = stageTypeMap[ps.stage_type_id];
          if (!stageName) return;
          if (projectStageSeq[ps.project_id] === undefined || ps.sequence_no > projectStageSeq[ps.project_id]) {
            projectStageSeq[ps.project_id] = ps.sequence_no;
            projectCurrentStage[ps.project_id] = stageName;
          }
        });

        const verticalMap: Record<string, string> = {};
        verticalsData.forEach((v) => { verticalMap[v.id] = v.vertical_name; });

        // --- PHASE 2: Enrich from monday.item_properties ---
        // Vertical, Project Status, and Atlas Project Stage are not yet written to
        // master_dashboard.projects by the backend, so read them directly from the
        // raw Monday staging table using the project's source_item_id.
        const mondayVertical: Record<string, string> = {};
        const mondayProjectStatus: Record<string, string> = {};
        const mondayAtlasStage: Record<string, string> = {};
        const mondayProjectStage: Record<string, string> = {};

        const itemIds = projectsData
          .map((p) => p.source_item_id)
          .filter((id): id is string => !!id);

        if (itemIds.length > 0) {
          const mondayBaseUrl = `${BASE_URL}/atlas/display/data?schema=monday&redact=off`;
          const mondayPropsRes = await fetch(
            `${mondayBaseUrl}&table=item_properties&limit=10000` +
              `&columns=monday_item_id,value_text,raw_json` +
              `&filter=monday_item_id:in:${itemIds.join(",")}`,
            { headers: authHeader }
          );
          if (mondayPropsRes.ok) {
            const mondayPropsJson = await mondayPropsRes.json();
            const mondayPropsData: MondayItemPropRow[] = mondayPropsJson.rows || [];
            mondayPropsData.forEach((prop) => {
              const title =
                prop.raw_json && typeof prop.raw_json === "object"
                  ? String((prop.raw_json as Record<string, unknown>).title ?? "")
                  : "";
              const val = prop.value_text?.trim() || "";
              const key = String(prop.monday_item_id);
              if (!val || !title) return;
              if (title === "Vertical") mondayVertical[key] = val;
              else if (title === "Project Status") mondayProjectStatus[key] = val;
              else if (title === "Atlas Project Stage") mondayAtlasStage[key] = val;
              else if (title === "Project Stage") mondayProjectStage[key] = val;
            });
          }
        }

        // --- CALCULATE CONTRACT EXPENDITURES PER PROJECT ---
        // Key by projects.id — the canonical FK referenced by contract_status.project_id
        const projectExpenditures: Record<string, number> = {};
        contractsData.forEach((contract) => {
          if (contract.project_id && contract.contract_amount) {
            const amount = Number(contract.contract_amount) || 0;
            projectExpenditures[contract.project_id] =
              (projectExpenditures[contract.project_id] || 0) + amount;
          }
        });

        // Store contracts for later use in detail panel
        setContracts(contractsData);

        // --- MERGE INTO ExtendedProject OBJECTS ---

        const formatted: ExtendedProject[] = projectsData.map((p) => {
          const itemId = p.source_item_id ?? "";

          // Status: DB fields first, then Monday raw value, then is_ongoing flag
          let statusCategory: ProjectStatus = "Ongoing";
          const rawStatus =
            p.status_category || p.project_status || mondayProjectStatus[itemId] || "";
          if (/hold/i.test(rawStatus)) statusCategory = "On Hold";
          else if (/archiv/i.test(rawStatus)) statusCategory = "Archived";
          else if (p.is_ongoing === false) statusCategory = "Archived";

          // Subtitle shown under the project name in the panel header
          const partnerNames = partnerStartupMap[p.id];
          const startupName = partnerNames?.length ? partnerNames.join(", ") : "";

          const description = p.description?.trim() || "No description available.";

          // Stage: DB fields → Monday raw atlas stage → Monday project stage → project_stages table
          const stageLabel =
            p.atlas_project_stage ||
            p.project_stage ||
            p.stage_name ||
            mondayAtlasStage[itemId] ||
            mondayProjectStage[itemId] ||
            projectCurrentStage[p.id] ||
            "";

          // Vertical: DB vertical_id FK → verticals table, else Monday raw value
          const rawVert =
            (p.vertical_id ? verticalMap[p.vertical_id] : null) ||
            mondayVertical[itemId] ||
            "";
          let verticalLabel: ProjectVertical = "Healthtech";
          if (/ai/i.test(rawVert)) verticalLabel = "AI";
          else if (/clean/i.test(rawVert)) verticalLabel = "Cleantech";

          // projects.id IS the canonical FK referenced by contract_status.project_id
          const linkId = p.id;

          const totalExpenditure = projectExpenditures[linkId] || 0;

          return {
            id: linkId,
            name: p.name || "Unnamed Project",
            description,
            startupName,
            stage: 2,
            status: stageLabel,
            vertical: verticalLabel,
            deadline: undefined,
            owner: p.tech_lead || (p.owner_id ? (peopleMap[p.owner_id] || "") : ""),
            stagesCompletedCY: [],
            statusCategory,
            totalExpenditure,
          };
        });

        setProjects(formatted);
      } catch (err) {
        console.error("Error loading projects:", err);
      } finally {
        setIsLoading(false);
      }
    }

    load();
  }, [projectBoardFilter]);

  // --- GET RELATED CONTRACTS FOR SELECTED PROJECT ---
  const getRelatedContracts = (project: ExtendedProject): ContractRow[] => {
    // contractProjectIdMap bridges projects.id → contract_status.project_id
    const matchId = contractProjectIdMap[project.id] || project.id;
    return contracts.filter((contract) => {
      if (contract.project_id) {
        return contract.project_id === matchId;
      }
      return !!(
        contract.contract &&
        project.name &&
        contract.contract.toLowerCase().includes(project.name.toLowerCase())
      );
    });
  };

  // Fetch budget-by-stage when a project is selected (for detail panel)
  useEffect(() => {
    if (!selectedProject?.id) {
      setBudgetByStage(null);
      return;
    }
    // Reset collapsed state so all stages open by default for each new project
    setCollapsedStages(new Set());
    let cancelled = false;
    const authHeader = { Authorization: `Bearer ${API_TOKEN}` };
    fetch(
      `${BASE_URL}/atlas/display/budget-by-stage?project_id=${encodeURIComponent(selectedProject.id)}`,
      { headers: authHeader }
    )
      .then((res) => {
        if (!res.ok) throw new Error(`Budget by stage: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled && data.rows) setBudgetByStage(data.rows);
      })
      .catch(() => {
        if (!cancelled) setBudgetByStage(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedProject?.id]);

  // --- FILTER LOGIC ---

  const filteredProjects = projects.filter((p) => {
    const q = query.toLowerCase();

    const matchesSearch =
      p.name.toLowerCase().includes(q) ||
      p.startupName.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q);

    let matchesFilters = true;

    if (
      filters.StatusCategory &&
      p.statusCategory.toLowerCase() !==
        String(filters.StatusCategory).toLowerCase()
    ) {
      matchesFilters = false;
    }

    if (
      filters.Stage &&
      !p.status.toLowerCase().startsWith(String(filters.Stage).toLowerCase())
    ) {
      matchesFilters = false;
    }

    if (
      filters.Company &&
      p.startupName.toLowerCase() !==
        String(filters.Company).toLowerCase()
    ) {
      matchesFilters = false;
    }

    if (
      filters.Vertical &&
      p.vertical.toLowerCase() !== String(filters.Vertical).toLowerCase()
    ) {
      matchesFilters = false;
    }

    if (
      filters.Owner &&
      p.owner.toLowerCase() !== String(filters.Owner).toLowerCase()
    ) {
      matchesFilters = false;
    }

    return matchesSearch && matchesFilters;
  });

  // Update chat context whenever projects data changes
  useEffect(() => {
    setContext({
      type: 'projects',
      data: {
        filteredProjects,
        selectedProject,
        filters,
        viewMode,
        totalProjects: projects.length,
      }
    });
  }, [projects, query, selectedProject, filters, viewMode, setContext]);

  // --- RENDER ---

  return (
    <div className="flex min-h-screen bg-white">
      <div className="flex-1 bg-gray-50 flex flex-col">
        <div className="bg-gray-50 px-4 pt-4 pb-3 border-b border-gray-100">
          <div className="mb-3 flex items-center justify-between">
            <h1 className="text-3xl font-extrabold text-gray-900">
              Projects
            </h1>
            <ViewToggle viewMode={viewMode} setViewMode={setViewMode} />
          </div>

          <SearchBar onSearch={setQuery} placeholder="Search Projects" />

          <ProjectFilterBar
            filters={filters}
            setFilters={setFilters}
            projects={projects}
          />
        </div>

        <div className="flex-1 overflow-y-auto px-4 pt-4 pb-8">
          <MainView
            viewMode={viewMode}
            projects={filteredProjects}
            isLoading={isLoading}
            onSelect={(p: ExtendedProject) => setSelectedProject(p)}
          />
        </div>
      </div>

      {selectedProject && (
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
                  {selectedProject.name}
                </h2>
                <p className="text-xs mt-1.5 line-clamp-3 leading-relaxed text-gray-500">
                  {selectedProject.startupName}
                </p>
              </div>
              <button
                onClick={() => setSelectedProject(null)}
                className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-gray-100 hover:bg-gray-200 text-gray-500 hover:text-gray-800 transition-colors text-xl leading-none font-light"
                aria-label="Close"
              >
                ×
              </button>
            </div>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

            {/* Project Details section */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 border border-blue-200 px-2.5 py-1 text-xs font-semibold text-blue-800 uppercase tracking-wide">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
                  Project Details
                </span>
              </div>
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <PanelField
                    label="Vertical"
                    value={
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                        selectedProject.vertical === "AI"
                          ? "bg-blue-100 text-blue-800"
                          : selectedProject.vertical === "Cleantech"
                          ? "bg-green-100 text-green-800"
                          : "bg-purple-100 text-purple-800"
                      }`}>
                        {selectedProject.vertical}
                      </span>
                    }
                  />
                  <PanelField label="Owner" value={selectedProject.owner || "—"} />
                  <PanelField label="Current Stage" value={selectedProject.status} />
                  <PanelField
                    label="Status Category"
                    value={
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                        selectedProject.statusCategory === "Ongoing"
                          ? "bg-emerald-100 text-emerald-800"
                          : selectedProject.statusCategory === "On Hold"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-gray-100 text-gray-600"
                      }`}>
                        {selectedProject.statusCategory}
                      </span>
                    }
                  />
                  <PanelField
                    label="Total Expenditure"
                    value={(() => {
                      const budgetTotal = budgetByStage?.reduce(
                        (sum, r) => sum + (Number(r.total_amount) || 0), 0
                      );
                      const amount = (budgetTotal && budgetTotal > 0)
                        ? budgetTotal
                        : selectedProject.totalExpenditure;
                      return amount > 0
                        ? new Intl.NumberFormat("en-US", {
                            style: "currency",
                            currency: "USD",
                            minimumFractionDigits: 0,
                            maximumFractionDigits: 0,
                          }).format(amount)
                        : "—";
                    })()}
                  />
                  <div className="col-span-2">
                    {(() => {
                      const desc = selectedProject.description || "";
                      const splitIdx = desc.search(/main customer[:\s]/i);
                      if (splitIdx === -1) {
                        return <PanelField label="Description" value={desc} />;
                      }
                      const body = desc.slice(0, splitIdx).trim();
                      const customerText = desc.slice(splitIdx).replace(/^main customer[:\s]*/i, "").trim();
                      return (
                        <div className="flex flex-col gap-2">
                          <PanelField label="Description" value={body} />
                          <div className="flex flex-col gap-0.5 min-w-0 bg-white rounded-md border border-blue-100 px-2.5 py-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-500 leading-none">
                              Main Customer
                            </span>
                            <span className="text-sm mt-0.5 text-gray-800">{customerText}</span>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              </div>
            </section>

            {/* Partner Startups */}
            <ProjectStartupsPanel
              entries={partnerStartupsByProject[selectedProject.id] ?? []}
              basePath="/app/partnerstartups"
            />

            {/* Related Contracts — grouped by stage */}
            {(() => {
              const relatedContracts = getRelatedContracts(selectedProject);
              if (relatedContracts.length === 0) return null;

              const fmt = (n: number) =>
                new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 0,
                }).format(n);

              // Group by stage label; use budget-by-stage totals when available
              const stageMap: Record<string, ContractRow[]> = {};
              relatedContracts.forEach((c) => {
                const key = (c.stage && String(c.stage).trim()) || "Unassigned";
                if (!stageMap[key]) stageMap[key] = [];
                stageMap[key].push(c);
              });

              // Merge any stages that appear in budget data but have no direct contracts
              if (budgetByStage) {
                budgetByStage.forEach((row) => {
                  if (!stageMap[row.stage_name]) stageMap[row.stage_name] = [];
                });
              }

              const grandTotal = relatedContracts.reduce(
                (sum, c) => sum + (Number(c.contract_amount) || 0),
                0
              );

              return (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-50 border border-amber-200 px-2.5 py-1 text-xs font-semibold text-amber-800 uppercase tracking-wide">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                      Related Contracts ({relatedContracts.length})
                    </span>
                  </div>

                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2">
                    {Object.entries(stageMap)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([stageName, stageContracts]) => {
                        const stageKey = `${selectedProject.id}-${stageName}`;
                        const isOpen = !collapsedStages.has(stageKey);

                        // Prefer server-aggregated total when available
                        const budgetRow = budgetByStage?.find(
                          (r) => r.stage_name === stageName
                        );
                        const stageTotal = budgetRow
                          ? Number(budgetRow.total_amount)
                          : stageContracts.reduce(
                              (sum, c) => sum + (Number(c.contract_amount) || 0),
                              0
                            );

                        return (
                          <div
                            key={stageName}
                            className="rounded-lg border border-amber-100 overflow-hidden shadow-sm"
                          >
                            {/* Stage header row — clickable */}
                            <button
                              className="w-full flex items-center justify-between px-3 py-2.5 bg-white hover:bg-amber-50 transition-colors text-sm"
                              onClick={() =>
                                setCollapsedStages((prev: Set<string>) => {
                                  const next = new Set(prev);
                                  if (next.has(stageKey)) next.delete(stageKey);
                                  else next.add(stageKey);
                                  return next;
                                })
                              }
                            >
                              <div className="flex items-center gap-2">
                                <span
                                  className="text-[#8B1E2F] text-xs transition-transform duration-200 inline-block"
                                  style={{ transform: isOpen ? "rotate(90deg)" : "rotate(0deg)" }}
                                >
                                  ▸
                                </span>
                                <span className="font-semibold text-gray-800">
                                  Stage {stageName}
                                </span>
                                <span className="text-xs text-gray-400">
                                  ({stageContracts.length})
                                </span>
                              </div>
                              <span className="font-bold tabular-nums text-amber-800">
                                {stageTotal > 0 ? fmt(stageTotal) : "—"}
                              </span>
                            </button>

                            {/* Expanded contracts */}
                            {isOpen && stageContracts.length > 0 && (
                              <div className="border-t border-amber-100 divide-y divide-amber-50">
                                {stageContracts.map((c) => (
                                  <div key={c.id} className="px-3 py-2.5 bg-white">
                                    <div className="flex justify-between items-start gap-2 mb-1">
                                      <span className="text-sm text-gray-800 flex-1 leading-snug">
                                        {c.contract}
                                      </span>
                                      <span className="text-sm font-semibold text-gray-700 whitespace-nowrap">
                                        {c.contract_amount ? fmt(Number(c.contract_amount)) : "—"}
                                      </span>
                                    </div>
                                    {(c.status_label || c.detail_scope) && (
                                      <div className="flex flex-wrap gap-1.5 text-xs">
                                        {c.status_label && (
                                          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                                            {c.status_label}
                                          </span>
                                        )}
                                        {c.detail_scope && (
                                          <span className="rounded-full bg-blue-50 px-2 py-0.5 font-medium text-blue-700">
                                            {c.detail_scope}
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}

                    {/* Grand total */}
                    <div className="pt-2 border-t border-amber-200 flex justify-between items-center px-1">
                      <span className="text-xs font-bold uppercase tracking-wider text-amber-800">
                        Total
                      </span>
                      <span className="font-bold text-gray-900 text-sm">
                        {fmt(grandTotal)}
                      </span>
                    </div>
                  </div>
                </section>
              );
            })()}
          </div>
        </aside>
      )}
    </div>
  );
}

function PanelField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 leading-none">
        {label}
      </span>
      <div className="text-sm mt-0.5 text-gray-800 break-words">{value ?? "—"}</div>
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

function MainView({
  viewMode,
  projects,
  isLoading,
  onSelect,
}: {
  viewMode: "cards" | "table";
  projects: ExtendedProject[];
  isLoading: boolean;
  onSelect: (p: ExtendedProject) => void;
}) {
  const [sortKey, setSortKey] = useState<string | null>(null);
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
    if (sortKey === null) {
      const STATUS_ORDER: Record<string, number> = {
        Ongoing: 0,
        "On Hold": 1,
        Archived: 2,
      };
      const sCat =
        (STATUS_ORDER[a.statusCategory] ?? 9) -
        (STATUS_ORDER[b.statusCategory] ?? 9);
      if (sCat !== 0) return sCat;

      const parseStage = (s: string) => {
        const m = s.match(/Stage (\d+)/i);
        return m ? parseInt(m[1], 10) : 999;
      };
      const aStage = parseStage(a.status);
      const bStage = parseStage(b.status);
      if (aStage !== bStage) return aStage - bStage;

      return a.name.localeCompare(b.name);
    }

    const aVal = (a as any)[sortKey];
    const bVal = (b as any)[sortKey];

    // Handle null/undefined
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return sortDirection === "asc" ? 1 : -1;
    if (bVal == null) return sortDirection === "asc" ? -1 : 1;

    // Handle numbers (like totalExpenditure)
    if (typeof aVal === "number" && typeof bVal === "number") {
      return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
    }

    // Handle strings
    const aStr = String(aVal).toLowerCase();
    const bStr = String(bVal).toLowerCase();
    if (aStr < bStr) return sortDirection === "asc" ? -1 : 1;
    if (aStr > bStr) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  if (isLoading) {
    return (
      <div className="text-center text-gray-500 py-12">
        Loading projects...
      </div>
    );
  }

  if (!projects || projects.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-gray-500">
        No projects match your filters.
      </div>
    );
  }

  if (viewMode === "cards") {
    const getStageNumber = (project: ExtendedProject): number => {
      const match = project.status.match(/Stage (\d+)/i);
      return match ? parseInt(match[1], 10) : 0;
    };

    const nonArchived = projects.filter((p) => p.statusCategory !== "Archived");
    const archived = projects.filter((p) => p.statusCategory === "Archived");

    // Group non-archived by stage
    const groupedProjects: Record<number, ExtendedProject[]> = {};
    nonArchived.forEach((project) => {
      const stageNum = getStageNumber(project);
      if (!groupedProjects[stageNum]) groupedProjects[stageNum] = [];
      groupedProjects[stageNum].push(project);
    });

    const stageOrder = [3, 4, 5, 6, 7, 8, 9];
    const orderedStages = stageOrder.filter((stage) => groupedProjects[stage]);

    // Group archived by stage, sort alphabetically within each group
    const archivedByStage: Record<number, ExtendedProject[]> = {};
    archived.forEach((project) => {
      const stageNum = getStageNumber(project);
      if (!archivedByStage[stageNum]) archivedByStage[stageNum] = [];
      archivedByStage[stageNum].push(project);
    });
    Object.values(archivedByStage).forEach((group) =>
      group.sort((a, b) => a.name.localeCompare(b.name))
    );
    const archivedStageNums = Object.keys(archivedByStage)
      .map(Number)
      .sort((a, b) => a - b);

    const ProjectGrid = ({ items }: { items: ExtendedProject[] }) => (
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
        {items.map((project) => (
          <div
            key={project.id}
            onClick={() => onSelect(project)}
            className="cursor-pointer"
          >
            <ProjectCard project={project} />
          </div>
        ))}
      </div>
    );

    return (
      <div className="space-y-8">
        {orderedStages.map((stageNum) => (
          <div key={stageNum}>
            <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b-2 border-gray-200">
              Stage {stageNum}
            </h2>
            <ProjectGrid items={groupedProjects[stageNum]} />
          </div>
        ))}

        {archivedStageNums.length > 0 && (
          <div>
            <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b-2 border-gray-200">
              Archived
            </h2>
            <div className="space-y-6">
              {archivedStageNums.map((stageNum) => (
                <div key={stageNum}>
                  <h3 className="text-base font-semibold text-gray-500 mb-3">
                    Stage {stageNum}
                  </h3>
                  <ProjectGrid items={archivedByStage[stageNum]} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  const cols = [
    { key: "name", label: "Name" },
    { key: "startupName", label: "Startup" },
    { key: "vertical", label: "Vertical" },
    { key: "owner", label: "Owner" },
    { key: "status", label: "Stage" },
    { key: "statusCategory", label: "Status" },
    { key: "totalExpenditure", label: "Expenditure" },
    { key: "deadline", label: "Deadline" },
    { key: "description", label: "Description" },
  ];

  const renderCell = (project: ExtendedProject, key: string) => {
    const value = (project as any)[key];

    if (key === "totalExpenditure") {
      const amount = project.totalExpenditure;
      if (!amount || amount === 0) return "—";
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(amount);
    }

    if (!value) return "—";

    if (key === "statusCategory") {
      const colors: Record<string, string> = {
        Ongoing: "bg-green-100 text-green-800",
        "On Hold": "bg-yellow-100 text-yellow-800",
        Archived: "bg-gray-100 text-gray-600",
      };
      return (
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
            colors[value] || "bg-gray-100 text-gray-600"
          }`}
        >
          {value}
        </span>
      );
    }

    if (key === "vertical") {
      const colors: Record<string, string> = {
        AI: "bg-blue-100 text-blue-800",
        Cleantech: "bg-green-100 text-green-800",
        Healthtech: "bg-purple-100 text-purple-800",
      };
      return (
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
            colors[value] || "bg-gray-100 text-gray-600"
          }`}
        >
          {value}
        </span>
      );
    }

    if (key === "description") {
      return (
        <span className="block max-w-[300px] truncate" title={String(value)}>
          {String(value)}
        </span>
      );
    }

    if (key === "deadline" && value) {
      return new Date(String(value)).toLocaleDateString();
    }

    return String(value);
  };

  return (
    <div className="overflow-auto bg-white rounded-xl shadow border border-gray-200">
      <table className="min-w-full text-sm border-collapse">
        <thead className="sticky top-0 z-10">
          <tr className="bg-(--color-custom-red)">
            {cols.map((col, i) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-[11px] font-bold text-white uppercase tracking-wider whitespace-nowrap cursor-pointer select-none hover:bg-red-900 transition-colors ${i === 0 ? "border-r border-white/20" : ""}`}
                onClick={() => handleSort(col.key)}
              >
                <div className="flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key && (
                    <span className="text-white/70">
                      {sortDirection === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedProjects.map((project, rowIdx) => (
            <tr
              key={project.id}
              className="group border-b cursor-pointer"
              onClick={() => onSelect(project)}
            >
              {cols.map((col, i) => (
                <td
                  key={col.key}
                  className={[
                    "px-4 py-2.5 align-top transition-colors group-hover:bg-rose-100",
                    rowIdx % 2 === 1 ? "bg-gray-50" : "bg-white",
                    i === 0 ? "font-semibold text-[#8B1E2F] border-r border-gray-100" : "text-gray-700",
                  ].join(" ")}
                >
                  {renderCell(project, col.key)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
