import type { Component } from "vue";

export type RewriteMode = "clamp" | "shift" | string;

export interface TargetForm {
  lat: number | null;
  lng: number | null;
  name: string;
  scale: number | null;
}

export interface FavoriteLocation {
  key: string;
  name: string;
  lat: number;
  lng: number;
  scale: number;
}

export interface RuntimeTarget {
  lat?: number;
  lng?: number;
  name?: string;
  scale?: number;
  mode?: RewriteMode;
}

export interface RuntimeState {
  enabled?: boolean;
  target?: RuntimeTarget;
  favorites?: Array<Partial<FavoriteLocation>>;
}

export interface PolicyRule {
  host?: string;
  paths?: string[];
  pass_through_other_paths?: boolean;
}

export interface Policy {
  allow?: PolicyRule[];
}

export interface Stats {
  request_total?: number;
  patch_success?: number;
  patch_noop?: number;
  pass_through_total?: number;
  patch_error?: number;
  reject_total?: number;
}

export interface LastPatch {
  patched?: boolean | string | number;
  old_center?: Array<string | number>;
  target?: Array<string | number>;
  reason?: string;
  sample?: string[];
}

export interface CertificateState {
  available?: boolean;
  url?: string;
}

export interface AppStatus {
  runtime?: RuntimeState;
  policy?: Policy;
  stats?: Stats;
  last_patch?: LastPatch | null;
  ca?: CertificateState;
  web?: {
    mode?: string;
  };
}

export interface RuntimeMutationResult {
  runtime?: RuntimeState;
}

export interface GenerateCaResult {
  restart_required?: boolean;
}

export type LogLevel = "success" | "warning" | "error" | "info" | string;

export interface LogEvent {
  id?: number;
  ts?: number;
  level?: LogLevel;
  layer?: string;
  source?: string;
  method?: string;
  host?: string;
  path?: string;
  status?: number | string;
  client?: string;
  type?: string;
  message?: string;
  details?: Record<string, unknown>;
}

export interface LogsResponse {
  events?: LogEvent[];
}

export interface MetricItem {
  label: string;
  value: number;
  tone: "info" | "success" | "neutral" | "danger" | "warning";
  icon: Component;
}

export interface LastPatchRow {
  label: string;
  value: string | number | boolean;
}

export interface GeocodeAddress {
  road?: string;
  pedestrian?: string;
  footway?: string;
  neighbourhood?: string;
  suburb?: string;
  city?: string;
  town?: string;
  village?: string;
  county?: string;
  state?: string;
  country?: string;
}

export interface GeocodeResult {
  place_id?: number | string;
  lat?: string | number;
  lon?: string | number;
  name?: string;
  display_name?: string;
  class?: string;
  type?: string;
  address?: GeocodeAddress;
}

export interface PickedLatLng {
  lat: number | null;
  lng: number | null;
  name: string;
  loading: boolean;
}

export interface PlaceSearchState {
  query: string;
  loading: boolean;
  results: GeocodeResult[];
  error: string;
}

export interface MessageApi {
  success(message: string): void;
  warning(message: string): void;
  error(message: string): void;
}
