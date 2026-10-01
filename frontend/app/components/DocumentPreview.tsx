import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

export interface AiResult {
  file_name: string;
  snippet: string;
  page: number | null;
  section_title: string | null;
  document_id: string;
  source_type: string;
  similarity: number | null;
  metadata: Record<string, unknown>;
}

interface Props {
  result: AiResult;
  fileUrl: string | undefined;
  query: string;
  onClose: () => void;
}

function highlightSnippet(text: string, query: string): string {
  if (!query.trim() || !text) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return text.replace(
    new RegExp(`(${escaped})`, "gi"),
    '<mark class="bg-yellow-200 rounded px-0.5">$1</mark>'
  );
}

function renderPdfText(str: string, query: string): string {
  if (!query.trim()) return str;
  const words = query.trim().split(/\s+/).filter(Boolean);
  const escaped = words
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  if (!escaped) return str;
  return str.replace(
    new RegExp(`(${escaped})`, "gi"),
    '<mark style="background:#fef08a;border-radius:2px;padding:0 1px">$1</mark>'
  );
}

export default function DocumentPreview({ result, fileUrl, query, onClose }: Props) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(result.page ?? 1);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const showPdf = Boolean(fileUrl) && pdfError === null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-4xl mx-4 flex flex-col"
        style={{ maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-200 flex-shrink-0">
          <div className="min-w-0 pr-8">
            <h2 className="text-lg font-bold text-gray-900 truncate">{result.file_name}</h2>
            <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
              {result.section_title && (
                <span>
                  Section:{" "}
                  <span className="font-medium text-gray-700">{result.section_title}</span>
                </span>
              )}
              {result.page != null && (
                <span>
                  Page:{" "}
                  <span className="font-medium text-gray-700">{result.page}</span>
                </span>
              )}
              {result.similarity != null && (
                <span>
                  Relevance:{" "}
                  <span
                    className={`font-medium ${
                      result.similarity >= 0.5 ? "text-green-700" : "text-amber-600"
                    }`}
                  >
                    {Math.round(result.similarity * 100)}%
                  </span>
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-xl font-bold leading-none flex-shrink-0"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* PDF viewer or text fallback */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {showPdf ? (
            <div className="flex flex-col items-center py-4 px-4">
              <Document
                file={fileUrl}
                onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                onLoadError={(err) => setPdfError(err.message ?? "Failed to load PDF")}
                loading={
                  <p className="text-sm text-gray-400 py-8 text-center">Loading PDF…</p>
                }
              >
                <Page
                  pageNumber={currentPage}
                  width={700}
                  renderAnnotationLayer
                  renderTextLayer
                  customTextRenderer={({ str }) => renderPdfText(str, query)}
                />
              </Document>
            </div>
          ) : (
            <div className="px-6 py-6">
              {pdfError && (
                <p className="text-xs text-red-500 mb-3">PDF failed to load: {pdfError}</p>
              )}
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">Matched snippet</p>
              <div
                className="text-sm text-gray-700 bg-gray-50 rounded-lg p-4 leading-relaxed border border-gray-100"
                dangerouslySetInnerHTML={{ __html: highlightSnippet(result.snippet, query) }}
              />
            </div>
          )}
        </div>

        {/* Page navigation */}
        {showPdf && numPages > 1 && (
          <div className="flex items-center justify-center gap-4 px-6 py-3 border-t border-gray-200 flex-shrink-0">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="px-3 py-1 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              ← Prev
            </button>
            <span className="text-sm text-gray-600 tabular-nums">
              Page {currentPage} of {numPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
              disabled={currentPage >= numPages}
              className="px-3 py-1 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        )}

        {/* Footer: snippet context + open link */}
        <div className="px-6 py-4 border-t border-gray-200 flex-shrink-0 bg-gray-50 rounded-b-xl">
          {showPdf && (
            <div className="mb-3">
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Matched snippet</p>
              <div
                className="text-xs text-gray-600 bg-white rounded p-3 border border-gray-100 leading-relaxed line-clamp-3"
                dangerouslySetInnerHTML={{ __html: highlightSnippet(result.snippet, query) }}
              />
            </div>
          )}
          {fileUrl && (
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
            >
              Open file
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
