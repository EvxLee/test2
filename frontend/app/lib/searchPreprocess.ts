export interface PreprocessResult {
  query: string;
  error: string | null;
}

/**
 * Normalizes a raw search query:
 * - Trims whitespace
 * - Lowercases
 * - Removes special characters (keeps letters, numbers, spaces)
 */
export function normalizeQuery(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, " ");
}

/**
 * Validates and normalizes a search query.
 * Returns the cleaned query on success, or an error message on failure.
 */
export function preprocessQuery(raw: string): PreprocessResult {
  if (!raw || raw.trim().length === 0) {
    return { query: "", error: "Query cannot be empty." };
  }

  const normalized = normalizeQuery(raw);

  if (normalized.length < 2) {
    return { query: "", error: "Query is too short. Please enter at least 2 characters." };
  }

  return { query: normalized, error: null };
}
