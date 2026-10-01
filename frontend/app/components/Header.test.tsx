import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Header from "./Header";

describe("Header", () => {
  it("renders with default props", () => {
    render(<Header />);
    expect(
      screen.getByText("Startup Sourcing Overview")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Combined totals across all GCED cycles")
    ).toBeInTheDocument();
  });

  it("renders custom title and subtitle", () => {
    render(<Header title="Custom Title" subtitle="Custom Sub" />);
    expect(screen.getByText("Custom Title")).toBeInTheDocument();
    expect(screen.getByText("Custom Sub")).toBeInTheDocument();
  });

  it("does not render subtitle when empty string is passed", () => {
    render(<Header subtitle="" />);
    expect(
      screen.getByText("Startup Sourcing Overview")
    ).toBeInTheDocument();
    expect(screen.queryByRole("paragraph")).not.toBeInTheDocument();
  });

  it("applies custom background color", () => {
    const { container } = render(<Header bgColor="#00FF00" />);
    const div = container.firstElementChild as HTMLElement;
    expect(div.style.backgroundColor).toBe("rgb(0, 255, 0)");
  });
});
