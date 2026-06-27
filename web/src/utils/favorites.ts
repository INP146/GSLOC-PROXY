import { formatNumber, normalizeLongitude } from "./format";
import type { FavoriteLocation, TargetForm } from "../types";

export function createFavoriteKey(lat: number, lng: number, name = ""): string {
  return `${Number(lat).toFixed(8)},${Number(lng).toFixed(8)},${name.trim()}`;
}

export function normalizeFavoriteLocation(
  raw?: Partial<FavoriteLocation> | TargetForm | null,
): FavoriteLocation | null {
  const lat = Number(raw?.lat);
  const lng = Number(raw?.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  const name = String(raw?.name || "").trim();
  const scale = Number(raw?.scale);
  return {
    key: createFavoriteKey(lat, lng, name),
    name,
    lat,
    lng: Number(normalizeLongitude(lng).toFixed(8)),
    scale: Number.isFinite(scale) ? scale : 1,
  };
}

export function formatFavoriteLabel(favorite: FavoriteLocation): string {
  return (
    favorite.name ||
    `${formatNumber(favorite.lat, 6)}, ${formatNumber(favorite.lng, 6)}`
  );
}
