import { useEffect, useState, useMemo } from "react";
import { useBoardConfig } from "app/lib/useBoardConfig";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

type Year = number;

interface GCEDStartupRow {
  id: string;
  monday_board_id: string;
  startup_name: string;
  track: string;
  team_decision: string;
  created_at: string;
}

interface CycleStats {
  label: string;
  verticals: { AI: number; CleanTech: number; HealthTech: number };
  statuses: { Yes: number; YesForLater: number; No: number };
  total: number;
}

const createEmptyStats = (label: string): CycleStats => ({
  label,
  verticals: { AI: 0, CleanTech: 0, HealthTech: 0 },
  statuses: { Yes: 0, YesForLater: 0, No: 0 },
  total: 0,
});


interface GCEDSummaryTableProps {
  onCycleClick?: (cycleKey: string, cycleLabel: string) => void;
}

export default function GCEDSummaryTable({ onCycleClick }: GCEDSummaryTableProps) {
  const { gcedCycles, availableYears } = useBoardConfig();
  const [allRows, setAllRows] = useState<GCEDStartupRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedYear, setSelectedYear] = useState<Year>(2025);

  useEffect(() => {
    if (availableYears.length > 0 && !availableYears.includes(selectedYear)) {
      setSelectedYear(availableYears[0]);
    }
  }, [availableYears, selectedYear]);

  // Fetch all data once
  useEffect(() => {
    async function load() {
      try {
        setIsLoading(true);

        let rows: GCEDStartupRow[] = [];
        let cursor: string | null = null;
        let hasMore = true;

        while (hasMore) {
          let apiUrl =
            `${BASE_URL}/atlas/display/data?schema=master_dashboard&table=gced_mftf25_startups&redact=off&limit=500`;
          if (cursor) apiUrl += `&cursor=${encodeURIComponent(cursor)}`;

          const res = await fetch(apiUrl, {
            headers: {
              Authorization: `Bearer ${API_TOKEN}`,
            },
          });

          if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);

          const json = await res.json();
          const pageRows = json.rows || [];

          rows = [...rows, ...pageRows];

          if (json.next_cursor) cursor = json.next_cursor;
          else hasMore = false;
        }

        setAllRows(rows);
      } catch (err) {
        console.error("Error loading dashboard data:", err);
      } finally {
        setIsLoading(false);
      }
    }

    load();
  }, []);

  // Filter cycles and compute stats based on selected year
  const data = useMemo(() => {
    const cyclesForYear = gcedCycles.filter(c => c.year === selectedYear);
    const boardIdsForYear = new Set(cyclesForYear.map(c => c.boardId));

    // Initialize stats
    const agg = createEmptyStats(`${selectedYear} Aggregated`);
    const cycleStats: CycleStats[] = cyclesForYear.map(cycle =>
      createEmptyStats(cycle.label)
    );

    // Build index map for filtered cycles
    const filteredBoardToIndex = new Map<string, number>();
    cyclesForYear.forEach((cycle, index) => {
      filteredBoardToIndex.set(cycle.boardId, index);
    });

    allRows.forEach((row) => {
      // Only process rows that belong to the selected year
      if (!boardIdsForYear.has(row.monday_board_id)) return;

      const cycleIndex = filteredBoardToIndex.get(row.monday_board_id);

      // Determine which buckets to update
      const buckets: CycleStats[] = [agg];
      if (cycleIndex !== undefined) {
        buckets.push(cycleStats[cycleIndex]);
      }

      buckets.forEach((bucket) => {
        bucket.total++;

        const track = (row.track || "").toLowerCase();
        if (track.includes("ai")) bucket.verticals.AI++;
        else if (track.includes("clean") || track.includes("energy"))
          bucket.verticals.CleanTech++;
        else if (track.includes("health") || track.includes("med"))
          bucket.verticals.HealthTech++;

        const decision = (row.team_decision || "").toLowerCase();
        if (decision === "yes") bucket.statuses.Yes++;
        else if (decision.includes("later"))
          bucket.statuses.YesForLater++;
        else if (decision === "no") bucket.statuses.No++;
      });
    });

    return {
      aggregated: agg,
      cycles: cycleStats,
      cycleConfigs: cyclesForYear,
    };
  }, [allRows, selectedYear, gcedCycles]);

  if (isLoading || !data) {
    return (
      <div className="p-10 text-center text-gray-500">
        Loading full dataset...
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Year Toggle */}
      <div className="flex justify-end">
        <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1 shadow-sm">
          {availableYears.map((year) => (
            <button
              key={year}
              type="button"
              onClick={() => setSelectedYear(year)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                selectedYear === year
                  ? "bg-[#8B2332] text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {year}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white shadow-lg rounded-xl overflow-hidden border border-gray-200">
        <div className="grid grid-cols-12 gap-4 bg-gray-50 border-b border-gray-200 py-4 px-6 text-xs uppercase tracking-wider font-bold text-gray-500">
          <div className="col-span-3">Cycle / Cohort</div>
          <div className="col-span-4">Startups by Vertical</div>
          <div className="col-span-3">Classification Status</div>
          <div className="col-span-2 text-center">Total Startups</div>
        </div>

        <div className="border-b border-gray-200 bg-gray-100/40">
          <StatsRow stats={data.aggregated} isMainRow={true} />
        </div>
        {data.cycles.length > 0 ? (
          data.cycles.map((cycleStats, index) => (
            <div key={data.cycleConfigs[index].key} className="border-b border-gray-100">
              <StatsRow
                stats={cycleStats}
                isMainRow={false}
                onClick={
                  onCycleClick
                    ? () => onCycleClick(data.cycleConfigs[index].key, data.cycleConfigs[index].label)
                    : undefined
                }
              />
            </div>
          ))
        ) : (
          <div className="px-6 py-8 text-center text-gray-500">
            No cycles configured for {selectedYear}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <SummaryCard
          label={`${selectedYear} Total Startups`}
          value={data.aggregated.total}
          textColor="text-[#8B2332]"
        />
        <SummaryCard
          label='Total "Yes"'
          value={data.aggregated.statuses.Yes}
          textColor="text-green-600"
        />
        <SummaryCard
          label='Total "Yes for Later"'
          value={data.aggregated.statuses.YesForLater}
          textColor="text-yellow-600"
        />
      </div>
    </div>
  );
}

function StatsRow({
  stats,
  isMainRow,
  onClick,
}: {
  stats: CycleStats;
  isMainRow: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      className={`grid grid-cols-12 gap-4 py-6 px-6 items-center transition-colors ${
        onClick ? "cursor-pointer hover:bg-gray-50" : "hover:bg-white"
      }`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      <div
        className={`col-span-3 flex items-center ${
          isMainRow ? "pl-0" : "pl-6"
        }`}
      >
        {isMainRow ? (
          <span className="font-extrabold text-lg text-gray-900">
            {stats.label}
          </span>
        ) : (
          <div className="flex items-center text-gray-600 font-medium">
            <span className="text-gray-300 mr-2">↳</span>
            {stats.label}
          </div>
        )}
      </div>

      <div className="col-span-4 space-y-2">
        <MiniStat label="AI" count={stats.verticals.AI} color="bg-blue-500" />
        <MiniStat
          label="CleanTech"
          count={stats.verticals.CleanTech}
          color="bg-green-500"
        />
        <MiniStat
          label="HealthTech"
          count={stats.verticals.HealthTech}
          color="bg-purple-500"
        />
      </div>

      <div className="col-span-3 space-y-2">
        <MiniStat label="Yes" count={stats.statuses.Yes} color="bg-green-500" />
        <MiniStat
          label="Later"
          count={stats.statuses.YesForLater}
          color="bg-yellow-500"
        />
        <MiniStat label="No" count={stats.statuses.No} color="bg-red-500" />
      </div>

      <div className="col-span-2 text-center">
        <span
          className={`block ${
            isMainRow
              ? "text-2xl font-black text-gray-800"
              : "text-xl font-bold text-gray-600"
          }`}
        >
          {stats.total}
        </span>
      </div>
    </div>
  );
}

/* ---------------- MINI STAT ---------------- */

function MiniStat({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: string;
}) {
  if (count === 0) return null;
  return (
    <div className="flex items-center justify-between max-w-[140px] text-sm">
      <span className="text-gray-500">{label}</span>
      <span
        className={`${color} text-white text-xs font-bold px-2 py-0.5 rounded-md min-w-[28px] text-center`}
      >
        {count}
      </span>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  textColor,
}: {
  label: string;
  value: number;
  textColor: string;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 flex flex-col items-center justify-center text-center">
      <h3 className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-2">
        {label}
      </h3>
      <span className={`text-4xl font-extrabold ${textColor}`}>{value}</span>
    </div>
  );
}
