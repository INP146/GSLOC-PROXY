export function formatNumber(value: unknown, precision = 6): string {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(precision) : "-";
}

export function normalizeLongitude(value: unknown): number {
  const number = Number(value);
  if (!Number.isFinite(number)) return number;
  return ((((number + 180) % 360) + 360) % 360) - 180;
}

export function formatTimestamp(ts?: number | null): string {
  if (!ts) return "-";
  const date = new Date(ts * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
