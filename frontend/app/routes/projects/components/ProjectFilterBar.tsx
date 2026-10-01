import React from "react";
import FilterSelect from "app/components/FilterSelect";

interface ProjectFilterBarProps {
  filters: any;
  setFilters: (filters: any) => void;
  projects: any[];
}

export default function ProjectFilterBar({
  filters,
  setFilters,
  projects,
}: ProjectFilterBarProps) {
  const handleChange = (key: string, value: string) => {
    setFilters({ ...filters, [key]: value });
  };

  const resetFilters = () => {
    setFilters({});
  };

  const owners = Array.from(
    new Set((projects || []).map((p) => p.owner).filter(Boolean))
  ).sort();

  const hasActiveFilters = Object.values(filters).some(Boolean);

  return (
    <div className="flex flex-wrap gap-2 items-center mt-3 bg-white px-3 py-2.5 rounded-xl border border-gray-200 shadow-sm">

      <FilterSelect
        value={filters.StatusCategory || ""}
        onChange={(e) => handleChange("StatusCategory", e.target.value)}
        active={!!filters.StatusCategory}
      >
        <option value="">All Status</option>
        <option value="Ongoing">Ongoing</option>
        <option value="Archived">Archived</option>
        <option value="On Hold">On Hold</option>
      </FilterSelect>

      <FilterSelect
        value={filters.Stage || ""}
        onChange={(e) => handleChange("Stage", e.target.value)}
        active={!!filters.Stage}
      >
        <option value="">All Stages</option>
        <option value="Stage 3">Stage 3</option>
        <option value="Stage 4">Stage 4</option>
        <option value="Stage 5">Stage 5</option>
        <option value="Stage 6">Stage 6</option>
        <option value="Stage 7">Stage 7</option>
        <option value="Stage 8">Stage 8</option>
        <option value="Stage 9">Stage 9</option>
      </FilterSelect>

      <FilterSelect
        value={filters.Vertical || ""}
        onChange={(e) => handleChange("Vertical", e.target.value)}
        active={!!filters.Vertical}
      >
        <option value="">All Verticals</option>
        <option value="AI">AI</option>
        <option value="Cleantech">Cleantech</option>
        <option value="Healthtech">Healthtech</option>
      </FilterSelect>

      <FilterSelect
        value={filters.Owner || ""}
        onChange={(e) => handleChange("Owner", e.target.value)}
        active={!!filters.Owner}
      >
        <option value="">All Owners</option>
        {owners.map((owner, i) => (
          <option key={i} value={owner}>
            {owner}
          </option>
        ))}
      </FilterSelect>

      {/* Reset Button */}
      <button
        onClick={resetFilters}
        className={`ml-auto flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
          hasActiveFilters
            ? "bg-[#8B1E2F] text-white hover:bg-[#7a1a29]"
            : "bg-gray-100 text-gray-500 hover:bg-gray-200"
        }`}
      >
        {hasActiveFilters && (
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        )}
        Reset
      </button>
    </div>
  );
}
