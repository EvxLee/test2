import { describe, it, expect } from "vitest";
import type Project from "~/types/Project";
import {
  sortProjects,
  groupByStatus,
  ytdStageCounts,
  countByCurrentStage,
} from "./projects";

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "1",
    name: "Test Project",
    description: "",
    startupName: "TestCo",
    stage: 3,
    status: "Active",
    statusCategory: "Ongoing",
    vertical: "AI",
    owner: "owner",
    stagesCompletedCY: [],
    ...overrides,
  };
}

describe("sortProjects", () => {
  it("sorts by status order: Ongoing < On Hold < Archived", () => {
    const archived = makeProject({ statusCategory: "Archived", name: "A" });
    const ongoing = makeProject({ statusCategory: "Ongoing", name: "B" });
    const onHold = makeProject({ statusCategory: "On Hold", name: "C" });

    const sorted = [archived, onHold, ongoing].sort(sortProjects);
    expect(sorted.map((p) => p.statusCategory)).toEqual([
      "Ongoing",
      "On Hold",
      "Archived",
    ]);
  });

  it("within same status, sorts by stage ascending", () => {
    const s2 = makeProject({ stage: 2, name: "A" });
    const s5 = makeProject({ stage: 5, name: "B" });
    const s3 = makeProject({ stage: 3, name: "C" });

    const sorted = [s2, s3, s5].sort(sortProjects);
    expect(sorted.map((p) => p.stage)).toEqual([2, 3, 5]);
  });

  it("within same status and stage, sorts by name ascending", () => {
    const c = makeProject({ name: "Charlie" });
    const a = makeProject({ name: "Alpha" });
    const b = makeProject({ name: "Bravo" });

    const sorted = [c, a, b].sort(sortProjects);
    expect(sorted.map((p) => p.name)).toEqual(["Alpha", "Bravo", "Charlie"]);
  });
});

describe("groupByStatus", () => {
  it("groups projects into the three status buckets", () => {
    const projects = [
      makeProject({ statusCategory: "Ongoing" }),
      makeProject({ statusCategory: "Archived" }),
      makeProject({ statusCategory: "On Hold" }),
      makeProject({ statusCategory: "Ongoing" }),
    ];

    const grouped = groupByStatus(projects);
    expect(grouped["Ongoing"]).toHaveLength(2);
    expect(grouped["On Hold"]).toHaveLength(1);
    expect(grouped["Archived"]).toHaveLength(1);
  });

  it("returns empty arrays when no projects match a status", () => {
    const grouped = groupByStatus([]);
    expect(grouped["Ongoing"]).toHaveLength(0);
    expect(grouped["On Hold"]).toHaveLength(0);
    expect(grouped["Archived"]).toHaveLength(0);
  });
});

describe("ytdStageCounts", () => {
  it("tallies stages completed in the current year", () => {
    const projects = [
      makeProject({ stagesCompletedCY: [2, 3] }),
      makeProject({ stagesCompletedCY: [3, 4] }),
      makeProject({ stagesCompletedCY: [5] }),
    ];

    expect(ytdStageCounts(projects)).toEqual({ 2: 1, 3: 2, 4: 1, 5: 1 });
  });

  it("returns zeros when no stages completed", () => {
    expect(ytdStageCounts([])).toEqual({ 2: 0, 3: 0, 4: 0, 5: 0 });
  });
});

describe("countByCurrentStage", () => {
  it("counts projects at each stage", () => {
    const projects = [
      makeProject({ stage: 2 }),
      makeProject({ stage: 2 }),
      makeProject({ stage: 4 }),
      makeProject({ stage: 5 }),
    ];

    expect(countByCurrentStage(projects)).toEqual({ 2: 2, 3: 0, 4: 1, 5: 1 });
  });

  it("ignores projects with null stage", () => {
    const projects = [
      makeProject({ stage: null }),
      makeProject({ stage: 3 }),
    ];

    expect(countByCurrentStage(projects)).toEqual({ 2: 0, 3: 1, 4: 0, 5: 0 });
  });
});
