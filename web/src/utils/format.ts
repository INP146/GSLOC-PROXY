export function formatNumber(value: unknown, precision = 6): string {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(precision) : "-";
}

export function normalizeLongitude(value: unknown): number {
  const number = Number(value);
  if (!Number.isFinite(number)) return number;
  return ((((number + 180) % 360) + 360) % 360) - 180;
}
