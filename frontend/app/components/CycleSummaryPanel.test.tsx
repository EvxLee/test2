import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import CycleSummaryPanel, {
  cycleKeyToBackendId,
} from "./CycleSummaryPanel";
import type { CycleSummaryResponse } from "~/types/CycleSummary";

/* ------------------------------------------------------------------ */
/*  cycleKeyToBackendId unit tests                                     */
/* ------------------------------------------------------------------ */

describe("cycleKeyToBackendId", () => {
  it("converts a standard cycle key to backend format", () => {
    expect(cycleKeyToBackendId("cycle7_2025")).toBe("gced_cycle7");
  });

  it("handles single-digit cycle numbers", () => {
    expect(cycleKeyToBackendId("cycle1_2025")).toBe("gced_cycle1");
  });

  it("handles double-digit cycle numbers", () => {
    expect(cycleKeyToBackendId("cycle12_2026")).toBe("gced_cycle12");
  });

  it("handles keys from different years", () => {
    expect(cycleKeyToBackendId("cycle3_2026")).toBe("gced_cycle3");
    expect(cycleKeyToBackendId("cycle5_2024")).toBe("gced_cycle5");
  });

  it("falls back to gced_cycle1 for malformed keys", () => {
    expect(cycleKeyToBackendId("invalid")).toBe("gced_cycle1");
  });
});

/* ------------------------------------------------------------------ */
/*  CycleSummaryPanel component tests                                  */
/* ------------------------------------------------------------------ */

const MOCK_RESPONSE: CycleSummaryResponse = {
  cycle_id: "gced_cycle7",
  summary: "This cycle featured 10 startups across AI and HealthTech verticals.",
  verticals: {
    AI: {
      total: 6,
      sub_categories: {
        "Agentic AI & Automation": 3,
        "Data Infrastructure & Curation": 2,
        "Other": 1,
      },
    },
    HealthTech: {
      total: 4,
      sub_categories: {
        "Clinical Decision Support & Diagnostics": 2,
        "Patient Engagement & Navigation": 2,
      },
    },
  },
  total_startups: 10,
};

describe("CycleSummaryPanel", () => {
  const originalFetch = global.fetch;
  let onClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onClose = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows loading skeleton initially", () => {
    // Never-resolving fetch to keep loading state
    global.fetch = vi.fn(() => new Promise(() => {}));

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    expect(screen.getByText("Generating AI summary...")).toBeInTheDocument();
    expect(screen.getByText("Cycle 7")).toBeInTheDocument();
    expect(screen.getByText("AI-Generated Summary")).toBeInTheDocument();
  });

  it("renders summary data after successful fetch", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_RESPONSE),
      })
    ) as unknown as typeof fetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText("This cycle featured 10 startups across AI and HealthTech verticals.")
      ).toBeInTheDocument();
    });

    // Check total startups
    expect(screen.getByText("10")).toBeInTheDocument();

    // Check vertical headers
    expect(screen.getByText("AI")).toBeInTheDocument();
    expect(screen.getByText("HealthTech")).toBeInTheDocument();

    // Check sub-category names
    expect(screen.getByText("Agentic AI & Automation")).toBeInTheDocument();
    expect(screen.getByText("Data Infrastructure & Curation")).toBeInTheDocument();
    expect(screen.getByText("Clinical Decision Support & Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Patient Engagement & Navigation")).toBeInTheDocument();
  });

  it("renders error state on API failure", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({
            error: "No startups found for cycle 'gced_cycle7'.",
          }),
      })
    ) as unknown as typeof fetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText("No startups found for cycle 'gced_cycle7'.")
      ).toBeInTheDocument();
    });

    // Should have a retry button
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders generic error when JSON parsing fails", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("not JSON")),
      })
    ) as unknown as typeof fetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load summary (HTTP 500)")
      ).toBeInTheDocument();
    });
  });

  it("calls onClose when close button is clicked", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_RESPONSE),
      })
    ) as unknown as typeof fetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    // Wait for fetch to complete so state updates don't fire after click
    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    const closeButton = screen.getByText("Close");
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("fetches with the correct backend cycle ID", async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_RESPONSE),
      })
    ) as unknown as typeof fetch;
    global.fetch = mockFetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle4_2025"
        cycleLabel="Cycle 4"
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/cycles/gced_cycle4/summary"),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: expect.stringContaining("Bearer"),
          }),
        })
      );
    });
  });

  it("retries fetch when retry button is clicked", async () => {
    let callCount = 0;
    global.fetch = vi.fn(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: "Server error" }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_RESPONSE),
      });
    }) as unknown as typeof fetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    // Wait for the error state
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });

    // Click retry
    fireEvent.click(screen.getByText("Retry"));

    // Should now show the data
    await waitFor(() => {
      expect(
        screen.getByText("This cycle featured 10 startups across AI and HealthTech verticals.")
      ).toBeInTheDocument();
    });
  });

  it("sorts sub-categories by count descending", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_RESPONSE),
      })
    ) as unknown as typeof fetch;

    render(
      <CycleSummaryPanel
        cycleKey="cycle7_2025"
        cycleLabel="Cycle 7"
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Agentic AI & Automation")).toBeInTheDocument();
    });

    // Verify the AI sub-categories appear in descending count order
    const aiSubCategories = ["Agentic AI & Automation", "Data Infrastructure & Curation", "Other"];
    const allText = document.body.textContent ?? "";
    const positions = aiSubCategories.map((name) => allText.indexOf(name));

    // Each position should be less than the next (order preserved in DOM)
    expect(positions[0]).toBeLessThan(positions[1]);
    expect(positions[1]).toBeLessThan(positions[2]);
  });
});
