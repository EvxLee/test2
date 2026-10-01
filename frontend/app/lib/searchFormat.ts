import type { SearchResultChunk, SearchResponse } from "app/data/mockSearchResults";

export interface FormattedResult {
  file_name: string;
  snippet: string;
  page: number;
}

export interface FormattedSearchResponse {
  results: FormattedResult[];
}

const SNIPPET_MAX_LENGTH = 150;

function buildSnippet(chunkText: string): string {
  const trimmed = chunkText.trim();
  if (trimmed.length <= SNIPPET_MAX_LENGTH) return trimmed;
  return trimmed.slice(0, SNIPPET_MAX_LENGTH).trimEnd() + "...";
}

function formatChunk(chunk: SearchResultChunk): FormattedResult {
  const fileName = (chunk.metadata.file_name as string) ?? "Unknown File";
  return {
    file_name: fileName,
    snippet: buildSnippet(chunk.chunk_text),
    page: chunk.page,
  };
}

export function formatSearchResponse(response: SearchResponse): FormattedSearchResponse {
  return {
    results: response.results.map(formatChunk),
  };
}
