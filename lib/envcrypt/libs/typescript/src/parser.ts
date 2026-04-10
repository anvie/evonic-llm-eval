/**
 * Parse a single env line: KEY=VALUE
 * Returns [key, value] or null if invalid.
 * Strips optional quotes from values.
 */
export function parseEnvLine(line: string): [string, string] | null {
  const eqPos = line.indexOf("=");
  if (eqPos === -1) return null;

  const key = line.slice(0, eqPos).trim();
  let value = line.slice(eqPos + 1).trim();

  if (key === "") return null;

  // Strip optional quotes
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }

  return [key, value];
}
