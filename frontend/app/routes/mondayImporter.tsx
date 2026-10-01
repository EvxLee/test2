import { useMemo, useState } from "react";
import { useBoardConfig } from "app/lib/useBoardConfig";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

interface IngestResult {
  status: "ok" | "error" | "partial";
  run_id: string;
  boards_processed: number;
  message?: string;
  summary?: {
    totals: {
      boards: number;
      items_staged: number;
      items_ins: number;
      items_upd: number;
      items_del: number;
      name_upd: number;
    };
    per_board?: Array<{
      board_id: string;
      staged_items: number;
      status: string;
    }>;
  };
  error?: {
    type: string;
    message: string;
  };
}

export default function MondayImporter() {
  const { gcedCycles, otherBoards, projectBoards } = useBoardConfig();
  const supportedBoards = useMemo(
    () => Array.from(new Map([...projectBoards, ...otherBoards].map((b) => [b.boardId, b])).values()),
    [otherBoards, projectBoards],
  );
  const [boardId, setBoardId] = useState<string>("");
  const [deleteHandling, setDeleteHandling] = useState<"soft" | "hard">("soft");
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleImport() {
    const trimmedBoardId = boardId.trim();
    if (!trimmedBoardId) {
      setError("Please enter a board ID.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${BASE_URL}/atlas/monday/ingest`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${API_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source: {
            type: "live",
            board_ids: [trimmedBoardId],
          },
          options: {
            handle_deletes: deleteHandling,
            dry_run: dryRun,
            verbose: true,
          },
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error?.message || `Request failed with status ${response.status}`);
        return;
      }

      setResult(data);
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Monday Data Importer</h1>
        <p className="text-gray-600 mb-6">
          Import data from Monday.com boards into the database.
        </p>

        {/* Supported Boards Reference */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
          <h3 className="text-sm font-semibold text-blue-900 mb-3">Supported Boards</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            {supportedBoards.map((b) => (
              <div key={b.boardId}>
                <p className="font-medium text-blue-800">{b.label}</p>
                <p className="text-blue-600 font-mono text-xs">{b.boardId}</p>
              </div>
            ))}
            {gcedCycles.map((c) => (
              <div key={c.boardId}>
                <p className="font-medium text-blue-800">GCED {c.label} - {c.year}</p>
                <p className="text-blue-600 font-mono text-xs">{c.boardId}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          {/* Board ID Input */}
          <div className="mb-6">
            <label htmlFor="board-id" className="block text-sm font-semibold text-gray-700 mb-2">
              Monday Board ID
            </label>
            <input
              type="text"
              id="board-id"
              value={boardId}
              onChange={(e) => setBoardId(e.target.value)}
              placeholder="Enter board ID (e.g., 1000000001)"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-900 focus:ring-2 focus:ring-[#8B1E2F] focus:border-[#8B1E2F] outline-none transition-all"
            />
            <p className="text-xs text-gray-500 mt-2">
              Find the board ID in the Monday.com URL: monday.com/boards/<strong>BOARD_ID</strong>
            </p>
          </div>

          {/* Options */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Options</h3>
            <div className="space-y-4">
              {/* Delete Handling */}
              <div className="flex items-center justify-between">
                <div>
                  <label htmlFor="delete-handling" className="text-sm text-gray-700 font-medium">
                    Delete Handling
                  </label>
                  <p className="text-xs text-gray-500">How to handle items removed from Monday</p>
                </div>
                <select
                  id="delete-handling"
                  value={deleteHandling}
                  onChange={(e) => setDeleteHandling(e.target.value as "soft" | "hard")}
                  className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-gray-900 text-sm focus:ring-2 focus:ring-[#8B1E2F] focus:border-[#8B1E2F] outline-none"
                >
                  <option value="soft">Soft (mark as deleted)</option>
                  <option value="hard">Hard (purge from database)</option>
                </select>
              </div>

              {/* Dry Run */}
              <div className="flex items-center justify-between">
                <div>
                  <label htmlFor="dry-run" className="text-sm text-gray-700 font-medium">
                    Dry Run
                  </label>
                  <p className="text-xs text-gray-500">Preview changes without committing</p>
                </div>
                <input
                  type="checkbox"
                  id="dry-run"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="w-5 h-5 text-[#8B1E2F] border-gray-300 rounded focus:ring-[#8B1E2F]"
                />
              </div>
            </div>
          </div>

          {/* Import Button */}
          <button
            onClick={handleImport}
            disabled={isLoading || !boardId.trim()}
            className={`w-full py-3 px-4 rounded-lg font-semibold text-white transition-all ${
              isLoading || !boardId.trim()
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-[#8B1E2F] hover:bg-[#6B1625] active:scale-[0.99]"
            }`}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <svg
                  className="animate-spin h-5 w-5"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Importing...
              </span>
            ) : (
              "Import Data"
            )}
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-red-800">Error</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Results Panel */}
        {result && (
          <div
            className={`rounded-xl border p-6 ${
              result.status === "ok"
                ? "bg-green-50 border-green-200"
                : result.status === "partial"
                ? "bg-yellow-50 border-yellow-200"
                : "bg-red-50 border-red-200"
            }`}
          >
            <div className="flex items-center gap-3 mb-4">
              {result.status === "ok" && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-green-100 text-green-800">
                  Success
                </span>
              )}
              {result.status === "partial" && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-yellow-100 text-yellow-800">
                  Partial Success
                </span>
              )}
              {result.status === "error" && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-red-100 text-red-800">
                  Error
                </span>
              )}
              {dryRun && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
                  Dry Run
                </span>
              )}
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Board ID:</span>
                <span className="font-mono text-gray-900">{boardId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Run ID:</span>
                <span className="font-mono text-gray-900">{result.run_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Boards Processed:</span>
                <span className="font-semibold text-gray-900">{result.boards_processed}</span>
              </div>
              {result.summary?.totals && (
                <>
                  <hr className="border-gray-200" />
                  <div className="flex justify-between">
                    <span className="text-gray-600">Items Staged:</span>
                    <span className="font-semibold text-gray-900">
                      {result.summary.totals.items_staged}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Items Inserted:</span>
                    <span className="font-semibold text-green-700">
                      {result.summary.totals.items_ins}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Items Updated:</span>
                    <span className="font-semibold text-blue-700">
                      {result.summary.totals.items_upd}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Items Deleted:</span>
                    <span className="font-semibold text-red-700">
                      {result.summary.totals.items_del}
                    </span>
                  </div>
                </>
              )}
              {result.message && (
                <>
                  <hr className="border-gray-200" />
                  <p className="text-gray-700">{result.message}</p>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
