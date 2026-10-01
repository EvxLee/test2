import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ProjectStartupsPanel from "./ProjectStartupsPanel";

const mockNavigate = vi.fn();

vi.mock("react-router", () => ({
  useNavigate: () => mockNavigate,
}));

const entries = [
  { startup_name: "Acme Corp", stage: "Stage 2" },
  { startup_name: "BioSynth", stage: "Stage 2" },
  { startup_name: "GreenTech AI", stage: "Stage 3" },
  { startup_name: "No Stage Co", stage: null },
];

beforeEach(() => {
  mockNavigate.mockClear();
});

describe("ProjectStartupsPanel", () => {
  it("renders section header with total count", () => {
    render(<ProjectStartupsPanel entries={entries} basePath="/app/partnerstartups" />);
    expect(screen.getByText(/Partner Startups/i)).toBeInTheDocument();
    expect(screen.getByText(/4/)).toBeInTheDocument();
  });

  it("renders all startup names", () => {
    render(<ProjectStartupsPanel entries={entries} basePath="/app/partnerstartups" />);
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("BioSynth")).toBeInTheDocument();
    expect(screen.getByText("GreenTech AI")).toBeInTheDocument();
    expect(screen.getByText("No Stage Co")).toBeInTheDocument();
  });

  it("groups startups under their stage label", () => {
    render(<ProjectStartupsPanel entries={entries} basePath="/app/partnerstartups" />);
    expect(screen.getByText("Stage 2")).toBeInTheDocument();
    expect(screen.getByText("Stage 3")).toBeInTheDocument();
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
  });

  it("navigates to basePath with startup query param on click", () => {
    render(<ProjectStartupsPanel entries={entries} basePath="/app/partnerstartups" />);
    fireEvent.click(screen.getByText("Acme Corp"));
    expect(mockNavigate).toHaveBeenCalledWith(
      "/app/partnerstartups?startup=Acme%20Corp"
    );
  });

  it("encodes special characters in startup name for navigation", () => {
    const special = [{ startup_name: "Bio & Synth / Labs", stage: "Stage 2" }];
    render(<ProjectStartupsPanel entries={special} basePath="/app/partnerstartups" />);
    fireEvent.click(screen.getByText("Bio & Synth / Labs"));
    expect(mockNavigate).toHaveBeenCalledWith(
      `/app/partnerstartups?startup=${encodeURIComponent("Bio & Synth / Labs")}`
    );
  });

  it("returns null when entries is empty", () => {
    const { container } = render(
      <ProjectStartupsPanel entries={[]} basePath="/app/partnerstartups" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("places entries with null stage under Unassigned group", () => {
    const nullStage = [{ startup_name: "No Stage Co", stage: null }];
    render(<ProjectStartupsPanel entries={nullStage} basePath="/app/partnerstartups" />);
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("No Stage Co")).toBeInTheDocument();
  });

  it("renders Unassigned group after named stages", () => {
    render(<ProjectStartupsPanel entries={entries} basePath="/app/partnerstartups" />);
    const stageHeaders = screen.getAllByText(/Stage \d+|Unassigned/);
    const lastHeader = stageHeaders[stageHeaders.length - 1];
    expect(lastHeader.textContent).toBe("Unassigned");
  });

  it("renders per-stage count badge", () => {
    render(<ProjectStartupsPanel entries={entries} basePath="/app/partnerstartups" />);
    // Stage 2 has 2 entries, Stage 3 has 1, Unassigned has 1
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });
});
