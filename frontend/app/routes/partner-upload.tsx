import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { hasPartnerRole } from "../auth";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;

const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5 MB

interface ResultRow {
  [key: string]: string;
}

function parseCSV(text: string): ResultRow[] {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
  return lines.slice(1).map((line) => {
    const values = line.split(",").map((v) => v.trim().replace(/^"|"$/g, ""));
    const row: ResultRow = {};
    headers.forEach((h, i) => {
      row[h] = values[i] ?? "";
    });
    return row;
  });
}

export default function PartnerUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ResultRow[] | null>(null);
  const [rawCsv, setRawCsv] = useState<string | null>(null);

  useEffect(() => {
    if (!hasPartnerRole()) {
      navigate("/");
    }
  }, [navigate]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setError(null);
    setResults(null);
    setRawCsv(null);

    if (!selected) {
      setFile(null);
      return;
    }
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setError("Only CSV files are accepted.");
      setFile(null);
      return;
    }
    if (selected.size > MAX_FILE_BYTES) {
      setError("File exceeds the 5 MB limit.");
      setFile(null);
      return;
    }
    setFile(selected);
  }

  async function handleSubmit() {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    setResults(null);
    setRawCsv(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        setError("Authentication required. Please log in again.");
        return;
      }

      const response = await fetch(`${BASE_URL}/atlas/partners/check-duplicates`, {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: formData,
      });

      if (response.status === 401) {
        setError("Unauthorized. Please ensure you have the external-partner role assigned.");
        return;
      }
      if (response.status === 429) {
        setError("Rate limit reached. You can check up to 10 files per hour. Please try again later.");
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.error ?? `Unexpected error (status ${response.status}).`);
        return;
      }

      const csvText = await response.text();
      setRawCsv(csvText);
      setResults(parseCSV(csvText));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleDownload() {
    if (!rawCsv) return;
    const blob = new Blob([rawCsv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "duplicates_result.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const duplicateCount =
    results?.filter(
      (r) => r.is_website_duplicate === "True" || r.is_name_duplicate === "True"
    ).length ?? 0;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Duplicate Checker</h1>
        <p className="text-gray-600 mb-6">
          Upload a CSV with a <code className="bg-gray-100 px-1 rounded text-sm">Website</code> column
          to check which entries already exist in our database. Including a{" "}
          <code className="bg-gray-100 px-1 rounded text-sm">Companies</code> column enables fuzzy name matching.
        </p>

        {/* Upload Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="mb-5">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              CSV File <span className="font-normal text-gray-400">(max 5 MB)</span>
            </label>
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-[#8B1E2F] transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              {file ? (
                <p className="text-sm text-gray-800 font-medium">{file.name}</p>
              ) : (
                <p className="text-sm text-gray-500">Click to select a CSV file</p>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={handleFileChange}
            />
            <p className="text-xs text-gray-500 mt-2">
              Required column: <code className="bg-gray-100 px-1 rounded">Website</code>
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isLoading || !file}
            className={`w-full py-3 px-4 rounded-lg font-semibold text-white transition-all ${
              isLoading || !file
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
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Checking...
              </span>
            ) : (
              "Check for Duplicates"
            )}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <div className="flex items-start gap-3">
              <svg className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {results && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Results</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  {results.length} rows checked &mdash;{" "}
                  <span className="text-red-600 font-medium">{duplicateCount} duplicate{duplicateCount !== 1 ? "s" : ""}</span>
                  {" "}found
                </p>
              </div>
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download CSV
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    {Object.keys(results[0] ?? {}).map((col) => (
                      <th
                        key={col}
                        className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((row, i) => {
                    const isWebsiteDup = row.is_website_duplicate === "True";
                    const isNameDup = row.is_name_duplicate === "True";
                    const isDuplicate = isWebsiteDup || isNameDup;
                    return (
                      <tr
                        key={i}
                        className={`border-b border-gray-100 ${isDuplicate ? "bg-red-50" : ""}`}
                      >
                        {Object.entries(row).map(([col, val]) => (
                          <td key={col} className="py-2 px-3 text-gray-800">
                            {col === "is_website_duplicate" ? (
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                                  isWebsiteDup
                                    ? "bg-red-100 text-red-700"
                                    : "bg-green-100 text-green-700"
                                }`}
                              >
                                {isWebsiteDup ? "Duplicate" : "Unique"}
                              </span>
                            ) : col === "is_name_duplicate" ? (
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                                  isNameDup
                                    ? "bg-orange-100 text-orange-700"
                                    : "bg-green-100 text-green-700"
                                }`}
                              >
                                {isNameDup ? "Possible match" : "Unique"}
                              </span>
                            ) : (
                              val
                            )}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
