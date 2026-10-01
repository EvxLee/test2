import { describe, it, expect } from "vitest";
import { findStartupByName } from "./findStartupByName";

interface NamedItem {
  name: string;
}

const startups: NamedItem[] = [
  { name: "Acme Corp" },
  { name: "BioSynth Solutions" },
  { name: "Green-Tech AI" },
  { name: "DeepMind Labs" },
  { name: "startup with  extra spaces" },
];

describe("findStartupByName", () => {
  it("returns the matching startup on exact case-insensitive match", () => {
    expect(findStartupByName(startups, "Acme Corp")).toBe(startups[0]);
    expect(findStartupByName(startups, "acme corp")).toBe(startups[0]);
    expect(findStartupByName(startups, "ACME CORP")).toBe(startups[0]);
  });

  it("returns the matching startup when names differ only in whitespace", () => {
    expect(findStartupByName(startups, "  Acme Corp  ")).toBe(startups[0]);
  });

  it("falls back to stripped alphanumeric comparison", () => {
    // "Green-Tech AI" stripped = "greentechai"
    // query "GreenTech AI" stripped = "greentechai"
    expect(findStartupByName(startups, "GreenTech AI")).toBe(startups[2]);
  });

  it("strips non-alphanumeric chars from both sides for fuzzy match", () => {
    // "BioSynth Solutions" stripped = "biosynthsolutions"
    // "BioSynth-Solutions" stripped = "biosynthsolutions"
    expect(findStartupByName(startups, "BioSynth-Solutions")).toBe(startups[1]);
  });

  it("returns undefined when no match found", () => {
    expect(findStartupByName(startups, "Unknown Startup")).toBeUndefined();
  });

  it("returns undefined for empty query", () => {
    expect(findStartupByName(startups, "")).toBeUndefined();
  });

  it("returns undefined for whitespace-only query", () => {
    expect(findStartupByName(startups, "   ")).toBeUndefined();
  });

  it("works with an empty startups array", () => {
    expect(findStartupByName([], "Acme Corp")).toBeUndefined();
  });

  it("handles startups with extra internal spaces via stripped match", () => {
    // "startup with  extra spaces" stripped = "startupwithextraspaces"
    // "startup with extra spaces" stripped  = "startupwithextraspaces"
    // Both strip to the same key — fuzzy match succeeds
    expect(findStartupByName(startups, "startup with extra spaces")).toBe(
      startups[4]
    );
  });

  it("returns the first match when two entries collide under stripped normalization", () => {
    const colliding = [
      { name: "BioSynth" },
      { name: "Bio-Synth" }, // both strip to "biosynth"
    ];
    // first-wins is the documented behavior
    expect(findStartupByName(colliding, "Bio Synth")).toBe(colliding[0]);
  });
});
