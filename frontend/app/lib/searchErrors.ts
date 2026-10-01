import type { FormattedSearchResponse } from "app/lib/searchFormat";

export interface SearchError {
  error: string;
  results?: never;
}

export type SearchResult = FormattedSearchResponse | SearchError;

export function isSearchError(result: SearchResult): result is SearchError {
  return "error" in result;
}

export function handleNoResults(): SearchError {
  return { error: "No matching documents found. Try different keywords." };
}

export function handleInvalidInput(message: string): SearchError {
  return { error: message };
}

export function handleBackendFailure(): SearchError {
  return { error: "Something went wrong. Please try again later." };
}

export function validateSearchResult(response: FormattedSearchResponse): SearchResult {
  if (!response.results || response.results.length === 0) {
    return handleNoResults();
  }
  return response;
}
