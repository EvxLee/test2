import { useState, useEffect, lazy, Suspense } from "react";
import SearchBar from "app/components/Searchbar";
import type { AiResult } from "~/components/DocumentPreview";

const DocumentPreview = lazy(() => import("~/components/DocumentPreview"));

const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;
const CONFIDENCE_THRESHOLD = 0.5;

interface Document {
  id: string;
  fileName: string;
  fileUrl: string;
  category: string;
  owner: string;
  lastUpdate: string;
  summary: string;
}

function highlightText(text: string, query: string): string {
  if (!query.trim() || !text) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return text.replace(
    new RegExp(`(${escaped})`, "gi"),
    '<mark class="bg-yellow-200 rounded px-0.5">$1</mark>'
  );
}

function friendlyError(err: unknown, status?: number): string {
  if (status === 401 || status === 403) return "Authentication failed. Please log in again.";
  if (status === 404) return "Document search service not found. Please contact support.";
  if (status != null && status >= 500) return "The AI search service encountered an error. Please try again.";
  if (err instanceof TypeError && err.message.includes("fetch"))
    return "Unable to connect to the server. Please check your connection.";
  return err instanceof Error ? err.message : "An unexpected error occurred.";
}

export default function DocumentsPage() {
  const [query, setQuery] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [aiResults, setAiResults] = useState<AiResult[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAiSearching, setIsAiSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [selectedResult, setSelectedResult] = useState<AiResult | null>(null);
  const [showWeakResults, setShowWeakResults] = useState(false);

  useEffect(() => {
    async function loadDocuments() {
      try {
        setIsLoading(true);
        setError(null);
        const url = `${BASE_URL}/atlas/display/data?schema=master_dashboard&redact=off&table=documents&columns=id,fileName,fileUrl,category,owner,lastUpdate,summary`;
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${API_TOKEN}` },
        });
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(friendlyError(null, response.status) + ` (${errorText})`);
        }
        const data = await response.json();
        setDocuments(data.rows && Array.isArray(data.rows) ? data.rows : []);
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setIsLoading(false);
      }
    }
    loadDocuments();
  }, []);

  async function handleSearch(q: string) {
    setQuery(q);
    setShowWeakResults(false);
    if (!q.trim()) {
      setAiResults(null);
      setAiError(null);
      return;
    }
    try {
      setIsAiSearching(true);
      setAiError(null);
      const response = await fetch(`${BASE_URL}/atlas/document-search`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${API_TOKEN}` },
        body: JSON.stringify({ query: q, source_type: "file" }),
      });
      if (!response.ok) throw Object.assign(new Error(), { status: response.status });
      const data = await response.json();
      setAiResults(data.results ?? []);
    } catch (err: any) {
      setAiError(friendlyError(err, err?.status));
      setAiResults(null);
    } finally {
      setIsAiSearching(false);
    }
  }

  const showingAiResults = aiResults !== null;

  const strongResults = aiResults
    ? aiResults.filter((r) => r.similarity === null || r.similarity >= CONFIDENCE_THRESHOLD)
    : [];
  const weakResults = aiResults
    ? aiResults.filter((r) => r.similarity !== null && r.similarity < CONFIDENCE_THRESHOLD)
    : [];

  const uniqueStrongFiles = Array.from(
    new Map(strongResults.map((r) => [r.file_name, r])).values()
  );

  const getFileUrl = (fileName: string) =>
    documents.find((d) => d.fileName === fileName)?.fileUrl;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Document preview modal */}
      {selectedResult && (
        <Suspense fallback={null}>
          <DocumentPreview
            result={selectedResult}
            query={query}
            fileUrl={getFileUrl(selectedResult.file_name)}
            onClose={() => setSelectedResult(null)}
          />
        </Suspense>
      )}

      {/* Header */}
      <div className="bg-gray-50 px-4 pt-4 pb-3 border-b border-gray-100">
        <div className="mb-3">
          <h1 className="text-3xl font-extrabold text-gray-900">Documents</h1>
        </div>
        {(error || aiError) && (
          <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error ?? aiError}
          </div>
        )}
        <SearchBar onSearch={handleSearch} placeholder="Search documents with AI…" submitOnly />
        {showingAiResults && (
          <p className="mt-2 text-xs text-gray-400">
            ✦ AI-powered results for:{" "}
            <span className="font-semibold text-gray-600">"{query}"</span>
            {" — "}
            <button
              className="underline hover:text-gray-800"
              onClick={() => {
                setAiResults(null);
                setQuery("");
                setShowWeakResults(false);
              }}
            >
              clear
            </button>
          </p>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-8">
        {(isLoading || isAiSearching) && (
          <p className="text-sm text-gray-500 py-4">
            {isAiSearching ? "Searching with AI…" : "Loading documents…"}
          </p>
        )}

        {!isLoading && !isAiSearching && !error && (
          <>
            <p className="mb-4 font-medium">
              {showingAiResults ? (
                strongResults.length > 0 ? (
                  <>
                    {strongResults.length} AI result{strongResults.length !== 1 ? "s" : ""} found
                    {weakResults.length > 0 && (
                      <span className="ml-2 text-sm font-normal text-amber-600">
                        +{weakResults.length} lower-confidence
                      </span>
                    )}
                  </>
                ) : weakResults.length > 0 ? (
                  <span className="text-amber-700">
                    No strong matches —{" "}
                    {weakResults.length} lower-confidence result{weakResults.length !== 1 ? "s" : ""} below
                  </span>
                ) : (
                  <span className="text-gray-500">No results found</span>
                )
              ) : (
                <>Showing all {documents.length} document{documents.length !== 1 ? "s" : ""}</>
              )}
            </p>

            {showingAiResults ? (
              <>
                {/* Strong results table */}
                <div className="overflow-x-auto border rounded-lg bg-white shadow-sm mb-4">
                  <table className="min-w-full border-collapse">
                    <thead>
                      <tr className="bg-(--color-custom-red) text-white text-left text-sm">
                        <th className="px-6 py-3 font-semibold">No.</th>
                        <th className="px-6 py-3 font-semibold">File Name</th>
                        <th className="px-6 py-3 font-semibold">Section</th>
                        <th className="px-6 py-3 font-semibold">Page</th>
                        <th className="px-6 py-3 font-semibold">Snippet</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strongResults.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                            {weakResults.length > 0
                              ? "No high-confidence matches. See lower-confidence results below."
                              : "No matching documents found. Try different search terms."}
                          </td>
                        </tr>
                      ) : (
                        strongResults.map((result, idx) => (
                          <tr
                            key={idx}
                            className={`cursor-pointer hover:bg-yellow-50 transition-colors ${idx % 2 === 0 ? "bg-gray-200" : "bg-gray-100"}`}
                            onClick={() => setSelectedResult(result)}
                            title="Click to preview"
                          >
                            <td className="px-6 py-4 text-sm font-medium">{idx + 1}</td>
                            <td className="px-6 py-4 text-sm font-medium">{result.file_name}</td>
                            <td className="px-6 py-4 text-sm">{result.section_title ?? "—"}</td>
                            <td className="px-6 py-4 text-sm">{result.page != null ? `p. ${result.page}` : "—"}</td>
                            <td
                              className="px-6 py-4 text-sm max-w-md truncate"
                              dangerouslySetInnerHTML={{ __html: highlightText(result.snippet, query) }}
                            />
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Lower-confidence results (collapsible) */}
                {weakResults.length > 0 && (
                  <div className="mb-4">
                    <button
                      onClick={() => setShowWeakResults((v) => !v)}
                      className="text-sm text-amber-600 hover:text-amber-800 flex items-center gap-1 mb-2 font-medium"
                    >
                      <span>{showWeakResults ? "▲" : "▼"}</span>
                      {weakResults.length} lower-confidence result{weakResults.length !== 1 ? "s" : ""}{" "}
                      (below {CONFIDENCE_THRESHOLD * 100}% relevance)
                    </button>
                    {showWeakResults && (
                      <div className="overflow-x-auto border border-amber-200 rounded-lg shadow-sm opacity-80">
                        <table className="min-w-full border-collapse">
                          <thead>
                            <tr className="bg-amber-600 text-white text-left text-sm">
                              <th className="px-6 py-3 font-semibold">No.</th>
                              <th className="px-6 py-3 font-semibold">File Name</th>
                              <th className="px-6 py-3 font-semibold">Section</th>
                              <th className="px-6 py-3 font-semibold">Page</th>
                              <th className="px-6 py-3 font-semibold">Snippet</th>
                            </tr>
                          </thead>
                          <tbody>
                            {weakResults.map((result, idx) => (
                              <tr
                                key={idx}
                                className={`cursor-pointer hover:bg-amber-100 transition-colors ${idx % 2 === 0 ? "bg-amber-50" : "bg-white"}`}
                                onClick={() => setSelectedResult(result)}
                                title="Click to preview"
                              >
                                <td className="px-6 py-4 text-sm font-medium">
                                  {strongResults.length + idx + 1}
                                </td>
                                <td className="px-6 py-4 text-sm font-medium">{result.file_name}</td>
                                <td className="px-6 py-4 text-sm">{result.section_title ?? "—"}</td>
                                <td className="px-6 py-4 text-sm">
                                  {result.page != null ? `p. ${result.page}` : "—"}
                                </td>
                                <td
                                  className="px-6 py-4 text-sm max-w-md truncate"
                                  dangerouslySetInnerHTML={{ __html: highlightText(result.snippet, query) }}
                                />
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Matched files */}
                {uniqueStrongFiles.length > 0 && (
                  <div className="overflow-x-auto border rounded-lg bg-white shadow-sm">
                    <div className="bg-(--color-custom-red) text-white text-sm px-6 py-3 font-semibold">
                      Files
                    </div>
                    <div className="flex flex-wrap gap-6 px-6 py-4">
                      {uniqueStrongFiles.map((file, idx) => {
                        const fileUrl = getFileUrl(file.file_name);
                        const inner = (
                          <div className="flex flex-col items-center gap-1 w-24">
                            <span className="text-3xl">📄</span>
                            <span className="text-xs text-center break-all text-gray-700">
                              {file.file_name}
                            </span>
                          </div>
                        );
                        return fileUrl ? (
                          <a
                            key={idx}
                            href={fileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:opacity-70 transition-opacity"
                          >
                            {inner}
                          </a>
                        ) : (
                          <div key={idx}>{inner}</div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="overflow-x-auto border rounded-lg bg-white shadow-sm">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-(--color-custom-red) text-white text-left text-sm">
                      <th className="px-6 py-4">No.</th>
                      <th className="px-6 py-4">File Name</th>
                      <th className="px-6 py-4">File</th>
                      <th className="px-6 py-4">Category</th>
                      <th className="px-6 py-4">Owner</th>
                      <th className="px-6 py-4">Last Update</th>
                      <th className="px-6 py-4">Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                          No documents found
                        </td>
                      </tr>
                    ) : (
                      documents.map((doc, idx) => (
                        <tr
                          key={doc.id || idx}
                          className={idx % 2 === 0 ? "bg-gray-200" : "bg-gray-100"}
                        >
                          <td className="px-6 py-4 text-sm font-medium">{idx + 1}</td>
                          <td className="px-6 py-4 text-sm font-medium">{doc.fileName}</td>
                          <td className="px-6 py-4 text-lg">
                            <a
                              href={doc.fileUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:opacity-70"
                              title={`Open ${doc.fileName}`}
                            >
                              📄
                            </a>
                          </td>
                          <td className="px-6 py-4 text-sm">{doc.category}</td>
                          <td className="px-6 py-4 text-sm">{doc.owner}</td>
                          <td className="px-6 py-4 text-sm">
                            {doc.lastUpdate
                              ? new Date(doc.lastUpdate).toLocaleDateString()
                              : "N/A"}
                          </td>
                          <td className="px-6 py-4 text-sm">{doc.summary}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
