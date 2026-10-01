// ============ BOARD CONFIGURATION ============
// Fallback values used when the /atlas/boards/config API is unavailable.
// Source of truth is the master_dashboard.board_config DB table.

export interface CycleConfig {
  key: string;
  label: string;
  boardId: string;
  year: number;
}

export interface BoardConfig {
  label: string;
  boardId: string;
}

export const PROJECT_BOARDS: BoardConfig[] = [
  { label: "Incubation Projects", boardId: "1000000001" },
  { label: "PJT Board IT", boardId: "10000000002" },
];

export const PROJECT_BOARD_IDS = PROJECT_BOARDS.map((b) => b.boardId);
export const PROJECT_BOARD_FILTER = `source_board:in:${PROJECT_BOARD_IDS.join(",")}`;

// GCED cycles ordered newest-first
export const GCED_CYCLES: CycleConfig[] = [
  { key: "cycle1_2026", label: "Cycle 1", boardId: "10000000021", year: 2026 },
  { key: "cycle7_2025", label: "Cycle 7", boardId: "10000000020", year: 2025 },
  { key: "cycle6_2025", label: "Cycle 6", boardId: "1000000019", year: 2025 },
  { key: "cycle5_2025", label: "Cycle 5", boardId: "1000000018", year: 2025 },
  { key: "cycle4_2025", label: "Cycle 4", boardId: "1000000017", year: 2025 },
  { key: "cycle3_2025", label: "Cycle 3", boardId: "1000000016", year: 2025 },
  { key: "cycle2_2025", label: "Cycle 2", boardId: "1000000015", year: 2025 },
  { key: "cycle1_2025", label: "Cycle 1", boardId: "1000000014", year: 2025 },
];

// Non-GCED boards
export const OTHER_BOARDS: BoardConfig[] = [
  ...PROJECT_BOARDS,
  { label: "Projects", boardId: "10000000007" },
  { label: "Contracts", boardId: "10000000008" },
  { label: "Regional", boardId: "10000000011" },
];

export const AVAILABLE_YEARS = [...new Set(GCED_CYCLES.map((c) => c.year))].sort(
  (a, b) => b - a,
);
