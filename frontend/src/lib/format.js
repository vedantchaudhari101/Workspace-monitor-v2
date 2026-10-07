/** Formatting helpers. Every function tolerates null and returns "—" for missing data. */

export const DASH = "—";

export function pct(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return `${Number(v).toFixed(digits)}%`;
}

export function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

/** 3725 → "1h 02m", 95 → "1m 35s", 12 → "12s". */
export function duration(seconds) {
  if (seconds === null || seconds === undefined) return DASH;
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(sec).padStart(2, "0")}s`;
  return `${sec}s`;
}

/** Video timestamp: 73.4 → "1:13". */
export function videoTime(seconds) {
  if (seconds === null || seconds === undefined) return DASH;
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function clock(iso, withSeconds = false) {
  if (!iso) return DASH;
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    ...(withSeconds ? { second: "2-digit" } : {}),
  });
}

export function dateTime(iso) {
  if (!iso) return DASH;
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function relative(iso) {
  if (!iso) return DASH;
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  return dateTime(iso);
}

/** 900 → "15 minutes", 3600 → "hour", 10800 → "3 hours". */
export function spanWords(seconds) {
  if (!seconds) return DASH;
  if (seconds % 3600 === 0) return seconds === 3600 ? "hour" : `${seconds / 3600} hours`;
  const m = Math.round(seconds / 60);
  return m === 1 ? "minute" : `${m} minutes`;
}

export function hourLabel(h) {
  return `${String(h).padStart(2, "0")}:00`;
}

export function plural(n, word, pluralWord) {
  return `${n} ${n === 1 ? word : pluralWord || `${word}s`}`;
}

export function bytes(n) {
  if (!n && n !== 0) return DASH;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export const statusLabel = {
  OCCUPIED: "Occupied",
  VACANT: "Available",
  UNKNOWN: "Not observed",
};

/** Natural sort for seat labels such as S2 < S10, A-01 < A-02. */
export function compareLabels(a, b) {
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}
