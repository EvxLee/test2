import { useEffect, useState, useCallback } from "react";
import type {
  CycleSummaryResponse,
  VerticalSummary,
} from "~/types/CycleSummary";

const BASE_URL = (import.meta.env.VITE_ATLAS_API_URL as string).replace(/\/$/, "");
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

interface CycleSummaryPanelProps {
  cycleKey: string;
  cycleLabel: string;
  onClose: () => void;
}

/**
 * Convert a frontend cycle key (e.g. "cycle7_2025") to the backend
 * cycle_id format (e.g. "gced_cycle7").
 */
export function cycleKeyToBackendId(key: string): string {
  const match = key.match(/cycle(\d+)/);
  const num = match ? match[1] : "1";
  return `gced_cycle${num}`;
}

const VERTICAL_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  AI: { dot: "bg-blue-500", bg: "bg-blue-50", text: "text-blue-700" },
  CleanTech: { dot: "bg-green-500", bg: "bg-green-50", text: "text-green-700" },
  HealthTech: { dot: "bg-purple-500", bg: "bg-purple-50", text: "text-purple-700" },
};

const VERTICAL_ORDER = ["AI", "CleanTech", "HealthTech"];

function getVerticalColor(vertical: string) {
  return VERTICAL_COLORS[vertical] ?? { dot: "bg-gray-500", bg: "bg-gray-50", text: "text-gray-700" };
}

export default function CycleSummaryPanel({
  cycleKey,
  cycleLabel,
  onClose,
}: CycleSummaryPanelProps) {
  const [data, setData] = useState<CycleSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; retryable: boolean } | null>(null);

  const fetchSummary = useCallback(
    (signal: AbortSignal) => {
      const backendId = cycleKeyToBackendId(cycleKey);
      setIsLoading(true);
      setError(null);
      setData(null);

      fetch(`${BASE_URL}/cycles/${backendId}/summary`, {
        headers: { Authorization: `Bearer ${API_TOKEN}` },
        signal,
      })
        .then(async (res) => {
          if (!res.ok) {
            const body = await res.json().catch(() => null);
            const message =
              body?.detail ??
              body?.error ??
              `Failed to load summary (HTTP ${res.status})`;
            const err = new Error(message);
            (err as Error & { status: number }).status = res.status;
            throw err;
          }
          return res.json();
        })
        .then((json: CycleSummaryResponse) => {
          setData(json);
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          const status = (err as Error & { status?: number }).status;
          setError({
            message:
              err instanceof Error ? err.message : "An unexpected error occurred",
            retryable: status !== 422,
          });
        })
        .finally(() => {
          setIsLoading(false);
        });
    },
    [cycleKey]
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchSummary(controller.signal);
    return () => controller.abort();
  }, [fetchSummary]);

  const handleRetry = () => {
    const controller = new AbortController();
    fetchSummary(controller.signal);
  };

  return (
    <aside className="fixed right-0 top-0 z-40 h-screen w-[420px] max-w-full bg-white border-l border-gray-100 shadow-xl p-6 overflow-y-auto transition-transform duration-300">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="pr-4">
          <h2 className="text-2xl font-semibold text-gray-900">
            {cycleLabel}
          </h2>
          <p className="text-sm text-gray-500 mt-1">AI-Generated Summary</p>
        </div>
        <button
          onClick={onClose}
          className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-3 py-1 rounded-lg text-sm"
        >
          Close
        </button>
      </div>

      <hr className="my-4 border-gray-100" />

      {/* Loading state */}
      {isLoading && <LoadingSkeleton />}

      {/* Error state */}
      {!isLoading && error && (
        <ErrorDisplay
          message={error.message}
          retryable={error.retryable}
          onRetry={handleRetry}
        />
      )}

      {/* Data state */}
      {!isLoading && !error && data && <SummaryContent data={data} />}
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <p className="text-sm text-gray-400">Generating AI summary...</p>
      <div className="h-4 bg-gray-200 rounded w-full" />
      <div className="h-4 bg-gray-200 rounded w-5/6" />
      <div className="h-4 bg-gray-200 rounded w-4/6" />
      <div className="mt-6 h-3 bg-gray-100 rounded w-1/3" />
      <div className="h-4 bg-gray-200 rounded w-full" />
      <div className="h-4 bg-gray-200 rounded w-3/4" />
      <div className="mt-4 h-3 bg-gray-100 rounded w-1/3" />
      <div className="h-4 bg-gray-200 rounded w-full" />
      <div className="h-4 bg-gray-200 rounded w-2/3" />
    </div>
  );
}

function ErrorDisplay({
  message,
  retryable,
  onRetry,
}: {
  message: string;
  retryable: boolean;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 p-4">
      <p className="text-sm text-red-700">{message}</p>
      {retryable && (
        <button
          onClick={onRetry}
          className="mt-3 text-sm font-medium text-red-600 hover:text-red-800 underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}

function SummaryContent({ data }: { data: CycleSummaryResponse }) {
  const sortedVerticals = VERTICAL_ORDER.filter(
    (v) => v in data.verticals
  );

  // Include any verticals not in the predefined order
  const extraVerticals = Object.keys(data.verticals).filter(
    (v) => !VERTICAL_ORDER.includes(v)
  );
  const allVerticals = [...sortedVerticals, ...extraVerticals];

  return (
    <div className="space-y-6">
      {/* Narrative summary */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2">
          Summary
        </h3>
        <p className="text-sm text-gray-700 leading-relaxed">
          {data.summary}
        </p>
      </div>

      {/* Total count */}
      <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
        <span className="text-sm font-medium text-gray-600">
          Total Startups Analyzed
        </span>
        <span className="text-lg font-bold text-gray-900">
          {data.total_startups}
        </span>
      </div>

      {/* Vertical breakdowns */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">
          Breakdown by Vertical
        </h3>
        <div className="space-y-4">
          {allVerticals.map((vertical) => (
            <VerticalSection
              key={vertical}
              name={vertical}
              data={data.verticals[vertical]}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function VerticalSection({
  name,
  data,
}: {
  name: string;
  data: VerticalSummary;
}) {
  const colors = getVerticalColor(name);

  const sortedSubCategories = Object.entries(data.sub_categories).sort(
    ([, a], [, b]) => b - a
  );

  return (
    <div className={`rounded-lg border border-gray-200 ${colors.bg} p-4`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${colors.dot}`} />
          <span className={`text-sm font-semibold ${colors.text}`}>
            {name}
          </span>
        </div>
        <span className={`text-xs font-bold ${colors.text}`}>
          {data.total} startup{data.total !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="space-y-1.5">
        {sortedSubCategories.map(([subCategory, count]) => (
          <div
            key={subCategory}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-gray-600 truncate pr-2">
              {subCategory}
            </span>
            <span className="text-gray-800 font-medium tabular-nums shrink-0">
              {count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
