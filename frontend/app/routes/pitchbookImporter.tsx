import { useState, useRef } from "react";

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

interface IngestResult {
  status: "ok" | "error";
  rows_read: number;
  rows_upserted: number;
  rows_skipped: number;
  error_samples?: string[];
}

export default function PitchbookImporter() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0] || null;
    if (selectedFile) {
      const ext = selectedFile.name.toLowerCase();
      if (!ext.endsWith(".csv") && !ext.endsWith(".xlsx")) {
        setError("File must be CSV or XLSX format.");
        setFile(null);
        return;
      }
    }
    setFile(selectedFile);
    setError(null);
    setResult(null);
  }

  async function handleImport() {
    if (!file) {
      setError("Please select a file.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${BASE_URL}/atlas/pitchbook/ingest`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${API_TOKEN}`,
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || `Request failed with status ${response.status}`);
        return;
      }

      setResult(data);
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleClear() {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">PitchBook Data Importer</h1>
        <p className="text-gray-600 mb-6">
          Import startup deal data from PitchBook exports into the database.
        </p>

        {/* Info Section */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">Supported Formats</h3>
          <div className="text-sm text-blue-800 space-y-1">
            <p><strong>CSV</strong> (.csv) - Standard comma-separated values</p>
            <p><strong>Excel</strong> (.xlsx) - Must have a sheet named "Data" with "Deal ID" header</p>
          </div>
          <p className="text-xs text-blue-600 mt-3">
            The importer will upsert records based on Deal ID. Existing records will be updated.
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          {/* File Input */}
          <div className="mb-6">
            <label htmlFor="file-input" className="block text-sm font-semibold text-gray-700 mb-2">
              Select File
            </label>
            <input
              ref={fileInputRef}
              type="file"
              id="file-input"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-900 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-[#8B1E2F] file:text-white hover:file:bg-[#6B1625] focus:ring-2 focus:ring-[#8B1E2F] focus:border-[#8B1E2F] outline-none transition-all"
            />
            {file && (
              <p className="text-sm text-gray-600 mt-2">
                Selected: <span className="font-medium">{file.name}</span> ({(file.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleImport}
              disabled={isLoading || !file}
              className={`flex-1 py-3 px-4 rounded-lg font-semibold text-white transition-all ${
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
            <button
              onClick={handleClear}
              disabled={isLoading}
              className="px-4 py-3 rounded-lg font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 transition-all"
            >
              Clear
            </button>
          </div>
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
                : "bg-yellow-50 border-yellow-200"
            }`}
          >
            <div className="flex items-center gap-3 mb-4">
              {result.status === "ok" ? (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-green-100 text-green-800">
                  Success
                </span>
              ) : (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-yellow-100 text-yellow-800">
                  Completed with Errors
                </span>
              )}
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Rows Read:</span>
                <span className="font-semibold text-gray-900">{result.rows_read}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Rows Upserted:</span>
                <span className="font-semibold text-green-700">{result.rows_upserted}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Rows Skipped:</span>
                <span className="font-semibold text-red-700">{result.rows_skipped}</span>
              </div>
            </div>

            {/* Error Samples */}
            {result.error_samples && result.error_samples.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Error Samples</h4>
                <ul className="space-y-2">
                  {result.error_samples.map((err, idx) => (
                    <li key={idx} className="text-xs text-red-700 bg-red-100 rounded p-2 font-mono break-all">
                      {err}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
