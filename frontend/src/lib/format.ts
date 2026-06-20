// Small display helpers shared across pages.

export function money(amount: number | null, currency: string | null): string {
  if (amount === null) return "—";
  const code = currency ?? "USD";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code,
    }).format(amount);
  } catch {
    // Unknown currency code — fall back to a plain number + code.
    return `${amount.toFixed(2)} ${code}`;
  }
}

export function monthLabel(month: string): string {
  // "2026-06" -> "Jun"
  const [year, m] = month.split("-").map(Number);
  const d = new Date(year, m - 1, 1);
  return d.toLocaleString(undefined, { month: "short" });
}

export function initials(name: string): string {
  // Ignore parenthetical suffixes, then first + last initial (max 2 letters).
  // "Anthropic (Claude Pro)" -> "A"; "Atlassian Jira" -> "AJ"
  const words = name
    .replace(/\(.*?\)/g, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0][0].toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

export function isoDate(date: string | null): string {
  if (!date) return "—";
  const d = new Date(date);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
