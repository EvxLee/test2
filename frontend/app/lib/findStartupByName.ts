function normalizeExact(v: string): string {
  return v.toLowerCase().trim();
}

function normalizeStripped(v: string): string {
  return v.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/**
 * Finds a startup from a list by name using two strategies:
 * 1. Case-insensitive, trimmed exact match
 * 2. Stripped alphanumeric fallback (ignores punctuation, spaces, hyphens)
 *
 * Returns undefined if no match found or query is empty.
 */
export function findStartupByName<T extends { name: string }>(
  startups: T[],
  query: string
): T | undefined {
  const trimmed = query.trim();
  if (!trimmed) return undefined;

  const exactKey = normalizeExact(trimmed);
  const exactMatch = startups.find((s) => normalizeExact(s.name) === exactKey);
  if (exactMatch) return exactMatch;

  const strippedKey = normalizeStripped(trimmed);
  if (!strippedKey) return undefined;

  return startups.find((s) => normalizeStripped(s.name) === strippedKey);
}
