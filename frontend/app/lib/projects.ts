import type Project from "~/types/Project";

type ProjectStatus = "Ongoing" | "On Hold" | "Archived";
type StageNum = 2 | 3 | 4 | 5;

const STATUS_ORDER: Record<ProjectStatus, number> = {
  "Ongoing": 0,
  "On Hold": 1,
  "Archived": 2,
};

export function sortProjects(a: Project, b: Project) {
  // 1) Status order: Ongoing -> On Hold -> Archived
  const s = STATUS_ORDER[a.statusCategory] - STATUS_ORDER[b.statusCategory];
  if (s !== 0) return s;

  // 2) Within status: Stage asc (3 -> 5), null stages last
  const aStage = a.stage ?? 999;
  const bStage = b.stage ?? 999;
  if (aStage !== bStage) return aStage - bStage;

  // 3) Tie-breaker: Name asc
  return a.name.localeCompare(b.name);
}

export function groupByStatus(data: Project[]) {
  return {
    Ongoing: data.filter((p) => p.statusCategory === "Ongoing"),
    "On Hold": data.filter((p) => p.statusCategory === "On Hold"),
    Archived: data.filter((p) => p.statusCategory === "Archived"),
  };
}

export function ytdStageCounts(projects: Project[]): Record<StageNum, number> {
  const counts: Record<StageNum, number> = { 2: 0, 3: 0, 4: 0, 5: 0 };

  for (const p of projects) {
    for (const st of p.stagesCompletedCY ?? []) {
      counts[st as StageNum] += 1;
    }
  }
  return counts;
}

export function countByCurrentStage(projects: Project[]): Record<StageNum, number> {
  const counts: Record<StageNum, number> = { 2: 0, 3: 0, 4: 0, 5: 0 };

  for (const p of projects) {
    if (p.stage && p.stage >= 2 && p.stage <= 5) {
      counts[p.stage as StageNum] += 1;
    }
  }
  return counts;
}
