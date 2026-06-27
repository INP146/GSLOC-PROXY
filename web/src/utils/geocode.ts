import { formatNumber, normalizeLongitude } from "./format";
import type { GeocodeResult } from "../types";

export function formatReverseGeocodeName(result?: GeocodeResult | null): string {
  const address = result?.address || {};
  const parts = [
    result?.name,
    address.road || address.pedestrian || address.footway,
    address.neighbourhood || address.suburb,
    address.city || address.town || address.village || address.county,
    address.state,
    address.country,
  ].filter(Boolean);
  return [...new Set(parts)].join("，") || result?.display_name || "";
}

export function formatSearchResultName(result?: GeocodeResult | null): string {
  return formatReverseGeocodeName(result) || result?.display_name || "";
}

export function formatSearchResultMeta(result?: GeocodeResult | null): string {
  const type = [result?.class, result?.type].filter(Boolean).join(" / ");
  const lat = formatNumber(result?.lat, 6);
  const lng = formatNumber(result?.lon, 6);
  return [type, `${lat}, ${lng}`].filter(Boolean).join(" · ");
}

export async function reverseGeocode(
  lat: number,
  lng: number,
): Promise<GeocodeResult> {
  const params = new URLSearchParams({
    format: "jsonv2",
    lat: String(lat),
    lon: String(normalizeLongitude(lng)),
    addressdetails: "1",
    namedetails: "1",
    "accept-language": "zh-CN,zh,en",
  });
  const response = await fetch(
    `https://nominatim.openstreetmap.org/reverse?${params}`,
    {
      headers: {
        Accept: "application/json",
      },
    },
  );
  if (!response.ok)
    throw new Error(`reverse geocode failed: ${response.status}`);
  return response.json() as Promise<GeocodeResult>;
}

export async function searchGeocodePlaces(
  query: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<GeocodeResult[]> {
  const params = new URLSearchParams({
    format: "jsonv2",
    q: query,
    limit: "8",
    addressdetails: "1",
    namedetails: "1",
    dedupe: "1",
    "accept-language": "zh-CN,zh,en",
  });
  const response = await fetch(
    `https://nominatim.openstreetmap.org/search?${params}`,
    {
      signal,
      headers: {
        Accept: "application/json",
      },
    },
  );
  if (!response.ok) throw new Error(`place search failed: ${response.status}`);
  return response.json() as Promise<GeocodeResult[]>;
}
