import { useState, useEffect } from "react";
import {
  GCED_CYCLES as FALLBACK_GCED,
  OTHER_BOARDS as FALLBACK_OTHER,
  PROJECT_BOARDS as FALLBACK_PROJECT,
  type CycleConfig,
  type BoardConfig,
} from "./boardConfig";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL as string;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN as string;
const PROJECT_BOARD_KEYS = new Set(["incubation_projects", "pjt_it"]);

interface BoardConfigResult {
  gcedCycles: CycleConfig[];
  otherBoards: BoardConfig[];
  projectBoards: BoardConfig[];
  projectBoardFilter: string;
  availableYears: number[];
  loading: boolean;
  error: string | null;
}

interface ApiBoardEntry {
  key?: string;
  board_key?: string;
  label: string;
  category: string;
  year: number | null;
  displayOrder?: number;
  display_order?: number;
  boardId?: string | null;
  board_id?: string | null;
}

interface BoardConfigState {
  gcedCycles: CycleConfig[];
  otherBoards: BoardConfig[];
  projectBoards: BoardConfig[];
}

const fallbackState: BoardConfigState = {
  gcedCycles: FALLBACK_GCED,
  otherBoards: FALLBACK_OTHER,
  projectBoards: FALLBACK_PROJECT,
};

let cachedState: BoardConfigState | null = null;
let cachedError: string | null = null;
let pendingRequest: Promise<BoardConfigState> | null = null;

function getBoardKey(board: ApiBoardEntry): string {
  return board.key || board.board_key || "";
}

function getBoardId(board: ApiBoardEntry): string {
  return (board.boardId || board.board_id || "").trim();
}

function toProjectBoardFilter(projectBoards: BoardConfig[]): string {
  const boardIds = projectBoards.map((b) => b.boardId).filter(Boolean);
  return `source_board:in:${boardIds.join(",")}`;
}

function toGcedCycles(boards: ApiBoardEntry[]): CycleConfig[] {
  return boards
    .filter((b) => b.category === "gced" && b.year !== null && getBoardId(b))
    .map((b) => ({
      key: getBoardKey(b),
      label: b.label,
      boardId: getBoardId(b),
      year: b.year as number,
    }));
}

function toOtherBoards(boards: ApiBoardEntry[]): BoardConfig[] {
  return boards
    .filter((b) => b.category === "other" && getBoardId(b))
    .map((b) => ({ label: b.label, boardId: getBoardId(b) }));
}

function toProjectBoards(boards: ApiBoardEntry[]): BoardConfig[] {
  return boards
    .filter((b) => PROJECT_BOARD_KEYS.has(getBoardKey(b)) && getBoardId(b))
    .map((b) => ({ label: b.label, boardId: getBoardId(b) }));
}

function withFallbacks(boards: ApiBoardEntry[]): BoardConfigState {
  const gcedCycles = toGcedCycles(boards);
  const otherBoards = toOtherBoards(boards);
  const projectBoards = toProjectBoards(boards);

  return {
    gcedCycles: gcedCycles.length ? gcedCycles : FALLBACK_GCED,
    otherBoards: otherBoards.length ? otherBoards : FALLBACK_OTHER,
    projectBoards: projectBoards.length ? projectBoards : FALLBACK_PROJECT,
  };
}

function fetchBoardConfig(): Promise<BoardConfigState> {
  if (cachedState) return Promise.resolve(cachedState);
  if (pendingRequest) return pendingRequest;

  pendingRequest = fetch(`${BASE_URL}/atlas/boards/config`, {
    headers: { Authorization: `Bearer ${API_TOKEN}` },
  })
    .then((res) => {
      if (!res.ok) throw new Error(`Failed to fetch board config: ${res.status}`);
      return res.json() as Promise<{ boards?: ApiBoardEntry[] }>;
    })
    .then((data) => {
      cachedState = withFallbacks(data.boards || []);
      cachedError = null;
      return cachedState;
    })
    .catch((err: Error) => {
      cachedError = err.message;
      cachedState = fallbackState;
      return cachedState;
    })
    .finally(() => {
      pendingRequest = null;
    });

  return pendingRequest;
}

export function useBoardConfig(): BoardConfigResult {
  const initialState = cachedState || fallbackState;
  const [gcedCycles, setGcedCycles] = useState<CycleConfig[]>(initialState.gcedCycles);
  const [otherBoards, setOtherBoards] = useState<BoardConfig[]>(initialState.otherBoards);
  const [projectBoards, setProjectBoards] = useState<BoardConfig[]>(initialState.projectBoards);
  const [loading, setLoading] = useState(!cachedState);
  const [error, setError] = useState<string | null>(cachedError);

  useEffect(() => {
    let cancelled = false;

    fetchBoardConfig()
      .then((state) => {
        if (cancelled) return;
        setGcedCycles(state.gcedCycles);
        setOtherBoards(state.otherBoards);
        setProjectBoards(state.projectBoards);
        setError(cachedError);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  const availableYears = [...new Set(gcedCycles.map((c) => c.year))].sort((a, b) => b - a);
  const projectBoardFilter = toProjectBoardFilter(projectBoards);

  return { gcedCycles, otherBoards, projectBoards, projectBoardFilter, availableYears, loading, error };
}
