import React from "react";
import FilterSelect from "./FilterSelect";

interface FilterBarProps {
  filters: any;
  setFilters: (filters: any) => void;
  startups: any[];
}

export default function FilterBar({ filters, setFilters, startups }: FilterBarProps) {
  const handleChange = (key: string, value: string) => {
    setFilters({ ...filters, [key]: value });
  };

  const resetFilters = () => {
    setFilters({});
  };

  // derive years from `founded` field in startups
  const years = Array.from(
    new Set(
      startups.map((s) => s.founded).filter(Boolean)
    )
  ).sort((a: any, b: any) => Number(b) - Number(a));

  // Extract unique years from the "LastFundingDate" column
  const fundingYears = Array.from(
    new Set(
      startups
        .map((d: any) => {
          if (!d.lastFundingDate) return null;
          const year = new Date(d.lastFundingDate).getFullYear();
          return isNaN(year) ? null : year;
        })
        .filter((y): y is number => typeof y === "number")
    )
  ).sort((a, b) => b - a);

  const hasActiveFilters = Object.values(filters).some(Boolean);

  return (
    <div className="flex flex-wrap gap-2 items-center mt-3 bg-white px-3 py-2.5 rounded-xl border border-gray-200 shadow-sm">

      {/* GCED Cycle Year Filter */}
      <FilterSelect
        value={filters["GCED Cycle Year"] || ""}
        onChange={(e) => handleChange("GCED Cycle Year", e.target.value)}
        active={!!filters["GCED Cycle Year"]}
      >
        <option value="">Cycle Year</option>
        <option value="2026">2026</option>
        <option value="2025">2025</option>
        <option value="2024">2024</option>
      </FilterSelect>

      {/* GCED Cycle Filter */}
      <FilterSelect
        value={filters["GCED Cycle"] || ""}
        onChange={(e) => handleChange("GCED Cycle", e.target.value)}
        active={!!filters["GCED Cycle"]}
      >
        <option value="">GCED Cycle</option>
        {[1, 2, 3, 4, 5, 6, 7].map((n) => (
          <option key={n} value={`Cycle ${n}`}>
            Cycle {n}
          </option>
        ))}
      </FilterSelect>

      {/* GCED Track Filter */}
      <FilterSelect
        value={filters["GCED Track"] || ""}
        onChange={(e) => handleChange("GCED Track", e.target.value)}
        active={!!filters["GCED Track"]}
      >
        <option value="">Track</option>
        {Array.from(
          new Set(
            startups
              .map((s) => s.gced_track)
              .filter(Boolean)
          )
        )
          .sort()
          .map((track: any) => (
            <option key={track} value={track.toLowerCase()}>
              {track}
            </option>
          ))}
      </FilterSelect>

      {/* Team Decision Filter */}
      <FilterSelect
        value={filters["Team Decision"] || ""}
        onChange={(e) => handleChange("Team Decision", e.target.value)}
        active={!!filters["Team Decision"]}
      >
        <option value="">Team Decision</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
        <option value="yes for later">Yes for Later</option>
      </FilterSelect>

      {/* Partner Status Filter */}
      <FilterSelect
        value={filters.FollowUp || ""}
        onChange={(e) => handleChange("FollowUp", e.target.value)}
        active={!!filters.FollowUp}
      >
        <option value="">Partner Status</option>
        <option value="Yes (working with CMBU)">Yes (working with CMBU)</option>
        <option value="No">No</option>
      </FilterSelect>

      {/* Average Score Filter */}
      <FilterSelect
        value={filters["Average Score"] || ""}
        onChange={(e) => handleChange("Average Score", e.target.value)}
        active={!!filters["Average Score"]}
      >
        <option value="">Avg Score</option>
        <option value="low">&le; 3</option>
        <option value="medium">3 – 4</option>
        <option value="high">&gt; 4</option>
      </FilterSelect>

      {/* Startup Source Filter */}
      <FilterSelect
        value={filters["Startup Source"] || ""}
        onChange={(e) => handleChange("Startup Source", e.target.value)}
        active={!!filters["Startup Source"]}
      >
        <option value="">Startup Source</option>
        {Array.from(
          new Set(
            startups
              .map((s) => s.gced_startup_source)
              .filter(Boolean)
          )
        )
          .sort()
          .map((source: any) => (
            <option key={source} value={source.toLowerCase()}>
              {source}
            </option>
          ))}
      </FilterSelect>

      {/* PitchBook Data Filter */}
      <FilterSelect
        value={filters["PitchBook Data"] || ""}
        onChange={(e) => handleChange("PitchBook Data", e.target.value)}
        active={!!filters["PitchBook Data"]}
      >
        <option value="">PitchBook Data</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </FilterSelect>

      {/* Industry Filter */}
      <FilterSelect
        value={filters.Industry || ""}
        onChange={(e) => handleChange("Industry", e.target.value)}
        active={!!filters.Industry}
      >
        <option value="">Verticals</option>
        <option value="Artificial Intelligence">AI</option>
        <option value="CleanTech">CleanTech</option>
        <option value="HealthTech">HealthTech</option>
      </FilterSelect>

      {/* Stage Filter */}
      <FilterSelect
        value={filters.Stage || ""}
        onChange={(e) => handleChange("Stage", e.target.value)}
        active={!!filters.Stage}
      >
        <option value="">All Stages</option>
        <option value="Angel">Angel</option>
        <option value="Seed">Seed</option>
        <option value="Series A">Series A</option>
        <option value="Series B">Series B</option>
        <option value="Venture - Unspecified">Venture - Unspecified</option>
      </FilterSelect>

      {/* Continent Filter */}
      <FilterSelect
        value={filters.Continent || ""}
        onChange={(e) => handleChange("Continent", e.target.value)}
        active={!!filters.Continent}
      >
        <option value="">Regions</option>
        <option value="Europe">Europe</option>
        <option value="Asia">Asia</option>
        <option value="North America">North America</option>
        <option value="South America">South America</option>
        <option value="Africa">Africa</option>
        <option value="Australia">Australia</option>
      </FilterSelect>

      {/* Year (founded) Filter */}
      <FilterSelect
        value={filters.Year || ""}
        onChange={(e) => handleChange("Year", e.target.value)}
        active={!!filters.Year}
      >
        <option value="">Year Founded</option>
        {years.map((y: any) => (
          <option key={y} value={String(y)}>
            {y}
          </option>
        ))}
      </FilterSelect>

      {/* Funds Raised Filter */}
      <FilterSelect
        value={filters["Total Raised"] || ""}
        onChange={(e) => handleChange("Total Raised", e.target.value)}
        active={!!filters["Total Raised"]}
      >
        <option value="">Funding</option>
        <option value="low">&le; $1M</option>
        <option value="mid">$1M – $10M</option>
        <option value="high">&ge; $10M</option>
      </FilterSelect>

      {/* Min Employees Filter */}
      <FilterSelect
        value={filters.MinEmployees || ""}
        onChange={(e) => handleChange("MinEmployees", e.target.value)}
        active={!!filters.MinEmployees}
      >
        <option value="">Employees</option>
        <option value="small">&lt;= 3</option>
        <option value="medium">4 – 50</option>
        <option value="large">&gt; 50</option>
      </FilterSelect>

      {/* Revenue Range */}
      <FilterSelect
        value={filters.RevenueRange || ""}
        onChange={(e) => handleChange("RevenueRange", e.target.value)}
        active={!!filters.RevenueRange}
      >
        <option value="">Revenue Range</option>
        <option value="low">&le; $1M</option>
        <option value="mid">$1M – $10M</option>
        <option value="mid-high">$10M – $100M</option>
        <option value="high">&gt; $100M</option>
      </FilterSelect>

      {/* Last Funding Date Filter */}
      <FilterSelect
        value={filters.LastFundingDate || ""}
        onChange={(e) => handleChange("LastFundingDate", e.target.value)}
        active={!!filters.LastFundingDate}
      >
        <option value="">Last Funding Year</option>
        {fundingYears.map((y: any) => (
          <option key={y} value={String(y)}>
            {y}
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
