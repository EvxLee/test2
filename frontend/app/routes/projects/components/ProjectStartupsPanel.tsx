import React from "react";
import { useNavigate } from "react-router";

interface StartupEntry {
  startup_name: string;
  stage: string | null;
}

interface Props {
  entries: StartupEntry[];
  basePath: string;
}

export default function ProjectStartupsPanel({ entries, basePath }: Props) {
  const navigate = useNavigate();

  if (entries.length === 0) return null;

  const grouped = entries.reduce<Record<string, StartupEntry[]>>((acc, entry) => {
    const key = entry.stage?.trim() || "Unassigned";
    return { ...acc, [key]: [...(acc[key] ?? []), entry] };
  }, {});

  const sortedStages = Object.keys(grouped).sort((a, b) => {
    if (a === "Unassigned") return 1;
    if (b === "Unassigned") return -1;
    return a.localeCompare(b);
  });

  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-violet-50 border border-violet-200 px-2.5 py-1 text-xs font-semibold text-violet-800 uppercase tracking-wide">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
          Partner Startups ({entries.length})
        </span>
      </div>

      <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 space-y-2">
        {sortedStages.map((stageName) => (
          <div
            key={stageName}
            className="rounded-lg border border-violet-100 overflow-hidden"
          >
            <div className="px-3 py-2 bg-white border-b border-violet-100 flex items-center justify-between">
              <span className="text-xs font-semibold text-violet-700 uppercase tracking-wide">
                {stageName}
              </span>
              <span className="text-xs text-gray-400">
                ({grouped[stageName].length})
              </span>
            </div>
            <div className="space-y-1 p-2">
              {grouped[stageName].map((entry) => (
                <button
                  key={entry.startup_name}
                  type="button"
                  className="w-full flex items-center rounded-md bg-white border border-violet-100 px-3 py-2 text-left hover:bg-violet-50 hover:border-violet-300 transition-colors cursor-pointer"
                  onClick={() =>
                    navigate(
                      `${basePath}?startup=${encodeURIComponent(entry.startup_name)}`
                    )
                  }
                >
                  <span className="text-sm font-medium text-gray-900 truncate">
                    {entry.startup_name}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
