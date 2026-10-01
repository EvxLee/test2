import { useEffect, useState } from "react";
import ColumnFilterDropdown, { type ColumnFilterOption } from "app/components/ColumnFilterDropdown";
import SearchBar from "app/components/Searchbar";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

interface ContractRow {
  id: string;
  contract: string;
  detail_scope: string | null;
  lms_number: string | null;
  contract_amount: number | null;
  start_date: string | null;
  end_date: string | null;
  requestor_id: string | null;
  status_label: string | null;
  priority_label: string | null;
  files_hint: string[] | null;
  signed_on: string | null;
  is_invoiced: boolean | null;
  invoiced_details: string | null;
  project_id?: string | null;
  project_stage_id?: string | null;
  stage?: string | null;
  category?: string | null;
  monday_item_id?: string | null;
  monday_item_name?: string | null;
  monday_board_id?: string | null;
  team?: string | null;
  pjt_task?: string | null;
  owner?: string | null;
}

interface ProjectRow {
  id: string;
  name: string;
  owner_id: string | null;
  stage_name: string | null;
}

interface PersonRow {
  id: string;
  full_name: string;
}

interface ProjectStageRow {
  id: string;
  project_id: string;
  stage_type_id: string;
}

interface StageTypeRow {
  id: string;
  stage_name: string;
}

interface BudgetByStageRow {
  project_id: string;
  project_name: string;
  stage_name: string;
  total_amount: number;
}

interface BoardFileRow {
  file_id: string;
  item_id: string;
  file_name: string;
  available: boolean;
  download_url?: string | null;
}

interface ContractDisplay extends ContractRow {
  projectName: string;
  ownerName: string;
  stageName: string;
  supportingFiles: BoardFileRow[];
}

interface BudgetStageGroup {
  stageName: string;
  amount: number;
  contracts: ContractDisplay[];
}

const CONTRACT_COLUMNS = [
  { key: "contract", label: "Contract" },
  { key: "contract_amount", label: "Contract Amount" },
  { key: "category", label: "Category", filterKey: "category" },
  { key: "stageName", label: "Stage", filterKey: "stage" },
  { key: "ownerName", label: "Owner", filterKey: "owner" },
  { key: "team", label: "Team", filterKey: "team" },
  { key: "pjt_task", label: "PJT / Task", filterKey: "projectTask" },
  { key: "files_hint", label: "Supporting Documents" },
  { key: "lms_number", label: "LMS" },
  { key: "period", label: "Period", filterKey: "period" },
];

const NON_PROJECT_BUDGET_KEYS = new Set(["marketing", "ces", "na", "n/a"]);

function normalizeExact(value: string | null | undefined): string {
  return (value || "").toLowerCase().trim();
}

function normalizeStripped(value: string | null | undefined): string {
  return (value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isConcreteStage(value: string | null | undefined): boolean {
  const normalized = normalizeExact(value);
  return Boolean(normalized && normalized !== "n/a" && normalized !== "unassigned");
}

function formatPeriod(start: string | null, end: string | null): string {
  if (start && end) return `${formatDate(start)} - ${formatDate(end)}`;
  if (start) return `From ${formatDate(start)}`;
  if (end) return `Until ${formatDate(end)}`;
  return "-";
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

function formatCurrency(amount: number | null): string {
  if (!amount) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function canonicalCategory(value: string | null | undefined): string {
  const normalized = normalizeExact(value);
  if (!normalized) return "";
  if (normalized === "agreement" || normalized === "agreements") return "agreements";
  if (normalized === "msa") return "msa";
  if (normalized === "contract") return "contract";
  return normalized;
}

function categoryLabel(value: string): string {
  if (value === "contract") return "Contract";
  if (value === "msa") return "MSA";
  if (value === "agreements") return "Agreements";
  return value;
}

function canonicalTeam(value: string | null | undefined): string {
  const normalized = normalizeExact(value);
  if (!normalized) return "others";
  if (["incubation", "marketing", "engineering", "planning", "gced"].includes(normalized)) {
    return normalized;
  }
  return "others";
}

function teamLabel(value: string): string {
  if (value === "others") return "Others";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function stageFilterValue(value: string | null | undefined): string {
  const trimmed = String(value || "").trim();
  return /^[2-7]$/.test(trimmed) ? trimmed : "";
}

function projectTaskValue(contract: ContractDisplay): string {
  return (contract.projectName || contract.pjt_task || "").trim();
}

function periodYears(contract: ContractDisplay): string[] {
  const years = new Set<string>();

  [contract.start_date, contract.end_date].forEach((value) => {
    if (!value) return;
    const year = new Date(value).getFullYear();
    if (!Number.isNaN(year)) years.add(String(year));
  });

  return Array.from(years);
}

export default function Contracts() {
  const [query, setQuery] = useState("");
  const [columnFilters, setColumnFilters] = useState<Record<string, string[]>>({});
  const [contracts, setContracts] = useState<ContractDisplay[]>([]);
  const [budgetByStage, setBudgetByStage] = useState<BudgetByStageRow[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<string>("contract");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    async function load() {
      try {
        setIsLoading(true);
        setError(null);

        const baseUrl = `${BASE_URL}/atlas/display/data?schema=master_dashboard&redact=off`;
        const authHeader = { Authorization: `Bearer ${API_TOKEN}` };

        const [contractsRes, projectsRes, peopleRes, projectStagesRes, stageTypesRes, budgetRes] =
          await Promise.all([
            fetch(
              `${baseUrl}&table=contract_status&limit=500&columns=` +
                [
                  "id",
                  "contract",
                  "detail_scope",
                  "lms_number",
                  "contract_amount",
                  "start_date",
                  "end_date",
                  "requestor_id",
                  "status_label",
                  "priority_label",
                  "files_hint",
                  "signed_on",
                  "is_invoiced",
                  "invoiced_details",
                  "project_id",
                  "project_stage_id",
                  "stage",
                  "category",
                  "monday_item_id",
                  "monday_item_name",
                  "monday_board_id",
                  "team",
                  "pjt_task",
                  "owner",
                ].join(","),
              { headers: authHeader }
            ),
            fetch(`${baseUrl}&table=projects&limit=1000&columns=id,name,owner_id,stage_name`, {
              headers: authHeader,
            }),
            fetch(`${baseUrl}&table=people&limit=500&columns=id,full_name`, {
              headers: authHeader,
            }),
            fetch(`${baseUrl}&table=project_stages&limit=2000&columns=id,project_id,stage_type_id`, {
              headers: authHeader,
            }),
            fetch(`${baseUrl}&table=stage_types&limit=100&columns=id,stage_name`, {
              headers: authHeader,
            }),
            fetch(`${BASE_URL}/atlas/display/budget-by-stage`, { headers: authHeader }),
          ]);

        if (!contractsRes.ok) {
          const errorText = await contractsRes.text();
          throw new Error(`Failed to load contracts: ${contractsRes.status} ${errorText}`);
        }

        const contractsJson = await contractsRes.json();
        const projectsJson = await projectsRes.json();
        const peopleJson = await peopleRes.json();
        const projectStagesJson = projectStagesRes.ok ? await projectStagesRes.json() : { rows: [] };
        const stageTypesJson = stageTypesRes.ok ? await stageTypesRes.json() : { rows: [] };
        const budgetJson = budgetRes.ok ? await budgetRes.json() : [];

        const contractsData: ContractRow[] = contractsJson.rows || [];
        const projectsData: ProjectRow[] = projectsJson.rows || [];
        const peopleData: PersonRow[] = peopleJson.rows || [];
        const projectStagesData: ProjectStageRow[] = projectStagesJson.rows || [];
        const stageTypesData: StageTypeRow[] = stageTypesJson.rows || [];
        const budgetData: BudgetByStageRow[] = Array.isArray(budgetJson)
          ? budgetJson
          : budgetJson.rows || [];

        const boardIds = Array.from(
          new Set(contractsData.map((contract) => contract.monday_board_id).filter(Boolean))
        ) as string[];

        const boardFilesResponses = await Promise.all(
          boardIds.map(async (boardId) => {
            const response = await fetch(
              `${BASE_URL}/atlas/display/monday/boards/${encodeURIComponent(boardId)}/files`,
              { headers: authHeader }
            );
            if (!response.ok) {
              return { boardId, files: [] as BoardFileRow[] };
            }
            const json = await response.json();
            return { boardId, files: (json.files || []) as BoardFileRow[] };
          })
        );

        const filesByBoardItem: Record<string, BoardFileRow[]> = {};
        boardFilesResponses.forEach(({ boardId, files }) => {
          files.forEach((file) => {
            if (!file.available || !file.download_url || !file.item_id) return;
            const fileKey = `${boardId}:${file.item_id}`;
            if (!filesByBoardItem[fileKey]) filesByBoardItem[fileKey] = [];
            filesByBoardItem[fileKey].push(file);
          });
        });

        const stageTypeMap: Record<string, string> = {};
        stageTypesData.forEach((stageType) => {
          stageTypeMap[stageType.id] = stageType.stage_name;
        });

        const projectStageMap: Record<string, string> = {};
        projectStagesData.forEach((projectStage) => {
          const stageName = stageTypeMap[projectStage.stage_type_id];
          if (stageName) projectStageMap[projectStage.id] = stageName;
        });

        const projectById: Record<string, ProjectRow> = {};
        const projectByName: Record<string, ProjectRow> = {};
        projectsData.forEach((project) => {
          projectById[project.id] = project;
          projectByName[project.name] = project;
        });

        const peopleMap: Record<string, string> = {};
        peopleData.forEach((person) => {
          peopleMap[person.id] = person.full_name;
        });

        const contractsWithMetadata: ContractDisplay[] = contractsData.map((contract) => {
          let matchedProject: ProjectRow | null = null;

          if (contract.project_id) {
            matchedProject = projectById[contract.project_id] ?? null;
          }

          if (!matchedProject) {
            for (const [projectName, project] of Object.entries(projectByName)) {
              if (contract.contract && contract.contract.toLowerCase().includes(projectName.toLowerCase())) {
                matchedProject = project;
                break;
              }
            }
          }

          const supportingFiles =
            filesByBoardItem[
              `${contract.monday_board_id || ""}:${contract.monday_item_id || ""}`
            ] || [];

          const ownerName =
            (contract.owner && String(contract.owner).trim()) ||
            (matchedProject?.owner_id ? peopleMap[String(matchedProject.owner_id)] : "") ||
            (contract.requestor_id ? peopleMap[String(contract.requestor_id)] : "") ||
            "";

          const stageName =
            (contract.project_stage_id && projectStageMap[contract.project_stage_id]) ||
            (contract.stage && String(contract.stage).trim()) ||
            matchedProject?.stage_name ||
            "";

          return {
            ...contract,
            projectName: matchedProject?.name || "",
            ownerName,
            stageName,
            supportingFiles,
          };
        });

        const contractsByBudgetKey: Record<string, ContractDisplay[]> = {};
        contractsWithMetadata.forEach((contract) => {
          const budgetKey = normalizeStripped(contract.projectName || contract.pjt_task);
          if (!budgetKey) return;
          if (!contractsByBudgetKey[budgetKey]) contractsByBudgetKey[budgetKey] = [];
          contractsByBudgetKey[budgetKey].push(contract);
        });

        const filteredBudgetData = budgetData.filter((row) => {
          const budgetKey = normalizeStripped(row.project_name);
          if (!budgetKey) return false;
          if (NON_PROJECT_BUDGET_KEYS.has(normalizeExact(row.project_name))) return false;

          const relatedContracts = contractsByBudgetKey[budgetKey] || [];
          if (relatedContracts.length === 0) return false;

          const hasConcreteProjectStage = relatedContracts.some((contract) =>
            isConcreteStage(contract.stageName || contract.stage)
          );
          const projectTotal = relatedContracts.reduce(
            (sum, contract) => sum + (Number(contract.contract_amount) || 0),
            0
          );

          return hasConcreteProjectStage && (relatedContracts.length > 1 || projectTotal >= 5000);
        });

        const canonicalProjectNames: Record<string, string> = {};
        filteredBudgetData.forEach((row) => {
          canonicalProjectNames[normalizeStripped(row.project_name)] = row.project_name;
        });

        const formattedContracts = contractsWithMetadata.map((contract) => ({
          ...contract,
          projectName:
            contract.projectName ||
            canonicalProjectNames[normalizeStripped(contract.pjt_task)] ||
            "",
        }));

        setBudgetByStage(filteredBudgetData);
        setContracts(formattedContracts);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Unknown error while loading contracts.";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }

    load();
  }, []);

  const categoryOptions: ColumnFilterOption[] = ["contract", "msa", "agreements"]
    .filter((value) => contracts.some((contract) => canonicalCategory(contract.category) === value))
    .map((value) => ({
      value,
      label: categoryLabel(value),
    }));

  const teamOptions: ColumnFilterOption[] = ["incubation", "marketing", "engineering", "planning", "gced", "others"]
    .filter((value) => contracts.some((contract) => canonicalTeam(contract.team) === value))
    .map((value) => ({
      value,
      label: teamLabel(value),
    }));

  const stageOptions: ColumnFilterOption[] = ["2", "3", "4", "5", "6", "7"]
    .filter((value) => contracts.some((contract) => stageFilterValue(contract.stageName || contract.stage) === value))
    .map((value) => ({
      value,
      label: value,
    }));

  const ownerOptions: ColumnFilterOption[] = Array.from(
    new Set(contracts.map((contract) => contract.ownerName).filter(Boolean))
  )
    .sort((a, b) => a.localeCompare(b))
    .map((value) => ({
      value,
      label: value,
      searchText: value,
    }));

  const projectTaskMap = new Map<string, { isProject: boolean; stages: Set<string> }>();
  contracts.forEach((contract) => {
    const name = projectTaskValue(contract);
    if (!name) return;

    const key = normalizeStripped(name);
    const stage = stageFilterValue(contract.stageName || contract.stage);
    const current = projectTaskMap.get(key) || { isProject: false, stages: new Set<string>() };

    if (contract.projectName) current.isProject = true;
    if (stage) current.stages.add(stage);

    projectTaskMap.set(key, current);
  });

  const projectTaskOptions: ColumnFilterOption[] = Array.from(projectTaskMap.entries())
    .map(([key, meta]) => {
      const sample = contracts.find((contract) => normalizeStripped(projectTaskValue(contract)) === key);
      const name = sample ? projectTaskValue(sample) : key;
      const sortedStages = Array.from(meta.stages).sort((a, b) => Number(a) - Number(b));
      const primaryStage = sortedStages[0];

      if (meta.isProject && primaryStage) {
        return {
          value: name,
          label: `${name} (Stage ${primaryStage})`,
          group: "Incubation",
          subgroup: `Stage ${primaryStage}`,
          searchText: `${name} ${sortedStages.join(" ")}`,
        };
      }

      return {
        value: name,
        label: `${name} (Task)`,
        group: "General tasks",
        searchText: name,
      };
    })
    .sort((a, b) => {
      const groupCompare = (a.group || "").localeCompare(b.group || "");
      if (groupCompare !== 0) return groupCompare;
      const subgroupCompare = (a.subgroup || "").localeCompare(b.subgroup || "");
      if (subgroupCompare !== 0) return subgroupCompare;
      return a.label.localeCompare(b.label);
    });

  const periodOptions: ColumnFilterOption[] = Array.from(
    new Set(contracts.flatMap((contract) => periodYears(contract)))
  )
    .sort((a, b) => Number(b) - Number(a))
    .map((value) => ({
      value,
      label: value,
      searchText: value,
    }));

  const filterOptionsByKey: Record<string, ColumnFilterOption[]> = {
    category: categoryOptions,
    team: teamOptions,
    stage: stageOptions,
    owner: ownerOptions,
    projectTask: projectTaskOptions,
    period: periodOptions,
  };

  const filteredContracts = contracts.filter((contract) => {
    const q = query.trim().toLowerCase();

    const matchesSearch =
      !q ||
      (contract.contract && contract.contract.toLowerCase().includes(q)) ||
      (contract.projectName && contract.projectName.toLowerCase().includes(q)) ||
      (contract.pjt_task && contract.pjt_task.toLowerCase().includes(q)) ||
      (contract.lms_number && contract.lms_number.toLowerCase().includes(q)) ||
      (contract.ownerName && contract.ownerName.toLowerCase().includes(q)) ||
      (contract.monday_item_name && contract.monday_item_name.toLowerCase().includes(q)) ||
      (contract.category && contract.category.toLowerCase().includes(q)) ||
      (contract.team && contract.team.toLowerCase().includes(q));

    const categoryMatches =
      !columnFilters.category?.length ||
      columnFilters.category.includes(canonicalCategory(contract.category));

    const teamMatches =
      !columnFilters.team?.length ||
      columnFilters.team.includes(canonicalTeam(contract.team));

    const stageMatches =
      !columnFilters.stage?.length ||
      columnFilters.stage.includes(stageFilterValue(contract.stageName || contract.stage));

    const ownerMatches =
      !columnFilters.owner?.length ||
      columnFilters.owner.includes(contract.ownerName);

    const projectTaskMatches =
      !columnFilters.projectTask?.length ||
      columnFilters.projectTask.includes(projectTaskValue(contract));

    const periodMatches =
      !columnFilters.period?.length ||
      periodYears(contract).some((year) => columnFilters.period.includes(year));

    return (
      matchesSearch &&
      categoryMatches &&
      teamMatches &&
      stageMatches &&
      ownerMatches &&
      projectTaskMatches &&
      periodMatches
    );
  });

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  const sortedContracts = [...filteredContracts].sort((a, b) => {
    const aVal = (a as unknown as Record<string, unknown>)[sortKey];
    const bVal = (b as unknown as Record<string, unknown>)[sortKey];

    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return sortDirection === "asc" ? 1 : -1;
    if (bVal == null) return sortDirection === "asc" ? -1 : 1;

    if (Array.isArray(aVal) && Array.isArray(bVal)) {
      return sortDirection === "asc" ? aVal.length - bVal.length : bVal.length - aVal.length;
    }

    if (typeof aVal === "number" && typeof bVal === "number") {
      return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
    }

    const aStr = String(aVal).toLowerCase();
    const bStr = String(bVal).toLowerCase();
    if (aStr < bStr) return sortDirection === "asc" ? -1 : 1;
    if (aStr > bStr) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  const budgetByProject: Record<
    string,
    { projectName: string; stages: BudgetStageGroup[]; total: number }
  > = {};

  budgetByStage.forEach((row) => {
    const budgetKey = normalizeStripped(row.project_name);
    const relatedContracts = contracts.filter(
      (contract) => normalizeStripped(contract.projectName || contract.pjt_task) === budgetKey
    );
    const stageContracts = relatedContracts.filter(
      (contract) => normalizeExact(contract.stageName || contract.stage) === normalizeExact(row.stage_name)
    );

    if (!budgetByProject[row.project_id]) {
      budgetByProject[row.project_id] = {
        projectName: row.project_name,
        stages: [],
        total: 0,
      };
    }

    budgetByProject[row.project_id].stages.push({
      stageName: row.stage_name,
      amount: Number(row.total_amount) || 0,
      contracts: stageContracts,
    });
    budgetByProject[row.project_id].total += Number(row.total_amount) || 0;
  });

  function renderCell(key: string, contract: ContractDisplay, rowIdx: number) {
    const cellKey = `${contract.id}-${key}`;
    const base = `px-4 py-2.5 align-top text-gray-700 transition-colors group-hover:bg-rose-50 ${
      rowIdx % 2 === 1 ? "bg-gray-50" : "bg-white"
    }`;

    switch (key) {
      case "contract":
        return (
          <td
            key={cellKey}
            className={`px-4 py-2.5 align-top sticky left-0 z-10 font-semibold text-[#8B1E2F] border-r border-gray-100 shadow-[2px_0_4px_-2px_rgba(0,0,0,0.06)] transition-colors group-hover:bg-rose-50 ${
              rowIdx % 2 === 1 ? "bg-gray-50" : "bg-white"
            }`}
          >
            {contract.contract || "-"}
          </td>
        );
      case "contract_amount":
        return <td key={cellKey} className={base}>{formatCurrency(Number(contract.contract_amount) || null)}</td>;
      case "category": {
        const category = contract.category?.trim().toLowerCase();
        const categoryChip =
          category === "contract" ? (
            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
              Contract
            </span>
          ) : category === "agreement" ? (
            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
              Agreement
            </span>
          ) : contract.category ? (
            <span>{contract.category}</span>
          ) : (
            <span>-</span>
          );
        return <td key={cellKey} className={base}>{categoryChip}</td>;
      }
      case "stageName":
        return <td key={cellKey} className={base}>{contract.stageName || "-"}</td>;
      case "ownerName":
        return <td key={cellKey} className={base}>{contract.ownerName || "-"}</td>;
      case "team":
        return <td key={cellKey} className={base}>{contract.team || "-"}</td>;
      case "pjt_task":
        return <td key={cellKey} className={base}>{contract.projectName || contract.pjt_task || "-"}</td>;
      case "files_hint": {
        const files = contract.supportingFiles;
        if (!files.length) return <td key={cellKey} className={base}>-</td>;

        return (
          <td key={cellKey} className={base}>
            <div className="flex flex-col gap-1">
              {files.map((file) => (
                <a
                  key={file.file_id}
                  href={file.download_url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 hover:underline text-xs truncate max-w-[200px]"
                  title={file.file_name}
                >
                  {file.file_name}
                </a>
              ))}
            </div>
          </td>
        );
      }
      case "lms_number":
        return <td key={cellKey} className={base}>{contract.lms_number || "-"}</td>;
      case "period":
        return <td key={cellKey} className={`${base} whitespace-nowrap min-w-[200px]`}>{formatPeriod(contract.start_date, contract.end_date)}</td>;
      default:
        return <td key={cellKey} className={base}>-</td>;
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-gray-50 px-4 pt-4 pb-3 border-b border-gray-100">
        <div className="mb-3">
          <h1 className="text-3xl font-extrabold text-gray-900">Contracts</h1>
        </div>

        {error && (
          <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            Error loading contracts: {error}
          </div>
        )}

        <SearchBar onSearch={setQuery} placeholder="Search Contracts" />
      </div>

      <div className="px-4 pt-4 pb-8">
        {isLoading ? (
          <div className="text-center text-gray-500 py-12">Loading contracts...</div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-600">Total Contracts</p>
                <p className="text-2xl font-bold text-gray-900">{filteredContracts.length}</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-600">Total Expenditure</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(
                    filteredContracts.reduce(
                      (sum, contract) => sum + (Number(contract.contract_amount) || 0),
                      0
                    )
                  )}
                </p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
                <p className="text-sm text-gray-600">Active Projects</p>
                <p className="text-2xl font-bold text-gray-900">
                  {Object.keys(budgetByProject).length}
                </p>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow border border-gray-200 overflow-hidden overflow-x-auto">
              <table className="text-sm border-collapse min-w-full">
                <thead className="sticky top-0 z-20">
                  <tr className="bg-(--color-custom-red)">
                    {CONTRACT_COLUMNS.map((column, index) => (
                      <th
                        key={column.key}
                        className={`px-4 py-3 text-left text-[11px] font-bold text-white uppercase tracking-wider whitespace-nowrap bg-(--color-custom-red) sticky top-0 select-none ${
                          index === 0 ? "left-0 z-30 border-r border-white/20" : "z-20"
                        }`}
                      >
                        <div className="flex flex-col items-start gap-1">
                          <button
                            type="button"
                            className="flex items-center gap-1 hover:text-white/80"
                            onClick={() => handleSort(column.key)}
                          >
                            <span>{column.label}</span>
                            {sortKey === column.key && (
                              <span className="text-white/70">
                                {sortDirection === "asc" ? "^" : "v"}
                              </span>
                            )}
                          </button>

                          {column.filterKey && (
                            <ColumnFilterDropdown
                              label="Filter"
                              options={filterOptionsByKey[column.filterKey]}
                              selected={columnFilters[column.filterKey] || []}
                              onChange={(values) =>
                                setColumnFilters((prev) => ({ ...prev, [column.filterKey!]: values }))
                              }
                              searchable={column.filterKey === "owner" || column.filterKey === "projectTask" || column.filterKey === "period"}
                              placeholder={
                                column.filterKey === "owner"
                                  ? "Search owners"
                                  : column.filterKey === "projectTask"
                                  ? "Search projects or tasks"
                                  : column.filterKey === "period"
                                  ? "Search year"
                                  : "Search"
                              }
                              widthClassName={column.filterKey === "projectTask" ? "w-80" : "w-64"}
                            />
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedContracts.length === 0 ? (
                    <tr>
                      <td
                        colSpan={CONTRACT_COLUMNS.length}
                        className="px-4 py-8 text-center text-gray-500"
                      >
                        No contracts match your filters.
                      </td>
                    </tr>
                  ) : (
                    sortedContracts.map((contract, rowIdx) => (
                      <tr key={contract.id} className="group border-b cursor-default">
                        {CONTRACT_COLUMNS.map((column) => renderCell(column.key, contract, rowIdx))}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {Object.keys(budgetByProject).length > 0 && (
              <div className="mt-6 bg-white rounded-xl shadow border border-gray-200 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                  <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">
                    Budget by Project &amp; Stage
                  </h2>
                  <div className="flex gap-6 text-[11px] font-bold text-gray-500 uppercase tracking-wider">
                    <span className="w-32 text-right">Total Spend</span>
                  </div>
                </div>

                <div className="divide-y divide-gray-100 p-4 space-y-3">
                  {Object.entries(budgetByProject)
                    .sort(([, a], [, b]) => b.total - a.total)
                    .map(([projectId, { projectName, stages, total }]) => {
                      const isExpanded = expandedProjects.has(projectId);
                      const toggle = () =>
                        setExpandedProjects((prev) => {
                          const next = new Set(prev);
                          if (next.has(projectId)) next.delete(projectId);
                          else next.add(projectId);
                          return next;
                        });

                      const grandTotal = stages.reduce((sum, stage) => sum + stage.amount, 0);

                      return (
                        <div
                          key={projectId}
                          className="rounded-lg border border-rose-200 overflow-hidden shadow-sm"
                        >
                          <button
                            className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-rose-50 transition-colors text-sm"
                            onClick={toggle}
                          >
                            <div className="flex items-center gap-2">
                              <span
                                className="text-[#8B1E2F] text-xs transition-transform duration-200 inline-block"
                                style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)" }}
                              >
                                {">"}
                              </span>
                              <span className="font-semibold text-[#8B1E2F]">{projectName}</span>
                            </div>
                            <span className="font-bold text-gray-900 tabular-nums">
                              {formatCurrency(total)}
                            </span>
                          </button>

                          {isExpanded && (
                            <div className="border-t border-rose-100 bg-rose-50 p-3 space-y-2">
                              {stages
                                .slice()
                                .sort((a, b) => b.amount - a.amount)
                                .map((stage) => {
                                  const stageContracts = stage.contracts;

                                  return (
                                    <div
                                      key={`${projectId}-${stage.stageName}`}
                                      className="rounded-lg border border-rose-100 overflow-hidden shadow-sm"
                                    >
                                      <div className="flex items-center justify-between px-3 py-2.5 bg-white text-sm">
                                        <div className="flex items-center gap-2">
                                          <span className="font-semibold text-gray-800">
                                            Stage {stage.stageName}
                                          </span>
                                          <span className="text-xs text-gray-400">
                                            ({stageContracts.length})
                                          </span>
                                        </div>
                                        <span className="font-bold tabular-nums text-[#8B1E2F]">
                                          {stage.amount > 0 ? formatCurrency(stage.amount) : "-"}
                                        </span>
                                      </div>

                                      {stageContracts.length > 0 && (
                                        <div className="border-t border-rose-100 divide-y divide-rose-50">
                                          {stageContracts.map((contract) => (
                                            <div
                                              key={contract.id}
                                              className="flex items-center justify-between px-3 py-2 bg-white hover:bg-rose-50 transition-colors"
                                            >
                                              <span className="text-sm text-gray-700 flex-1 leading-snug">
                                                {contract.contract || "-"}
                                              </span>
                                              <span className="text-sm font-medium text-gray-600 tabular-nums whitespace-nowrap ml-4">
                                                {contract.contract_amount
                                                  ? formatCurrency(Number(contract.contract_amount))
                                                  : "-"}
                                              </span>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}

                              <div className="pt-2 border-t border-rose-200 flex justify-between items-center px-1">
                                <span className="text-xs font-bold uppercase tracking-wider text-[#8B1E2F]">
                                  Total
                                </span>
                                <span className="font-bold text-gray-900 text-sm tabular-nums">
                                  {formatCurrency(grandTotal)}
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
