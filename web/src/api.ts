import type {
  AppStatus,
  AuthStatus,
  FavoriteLocation,
  GenerateCaResult,
  LoginPayload,
  LogsResponse,
  RewriteMode,
  RuntimeMutationResult,
  TargetForm,
} from "./types";

interface RequestJsonOptions {
  method?: string;
  body?: unknown;
  skipAuthRedirect?: boolean;
}

const AUTH_CHANGED_EVENT = "gsloc-auth-changed";
let csrfToken = "";

export function setCsrfToken(token?: string): void {
  csrfToken = token || "";
}

export function getCsrfToken(): string {
  return csrfToken;
}

export function notifyAuthChanged(): void {
  window.dispatchEvent(new CustomEvent(AUTH_CHANGED_EVENT));
}

export function onAuthChanged(callback: () => void): () => void {
  window.addEventListener(AUTH_CHANGED_EVENT, callback);
  return () => window.removeEventListener(AUTH_CHANGED_EVENT, callback);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

async function requestJson<T>(
  path: string,
  { method = "GET", body, skipAuthRedirect = false }: RequestJsonOptions = {},
): Promise<T> {
  const options: RequestInit = {
    method,
    credentials: "same-origin",
    headers: {},
  };

  if (method === "GET") {
    options.cache = "no-store";
  }

  if (body !== undefined) {
    (options.headers as Record<string, string>)["Content-Type"] =
      "application/json";
    options.body = JSON.stringify(body);
  }

  if (method !== "GET" && csrfToken) {
    (options.headers as Record<string, string>)["X-CSRF-Token"] = csrfToken;
  }

  let response: Response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    throw new Error(`无法连接后端管理 API：${errorMessage(err)}`);
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`后端返回了非 JSON 响应：${response.status}`);
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !skipAuthRedirect) {
      setCsrfToken("");
      notifyAuthChanged();
    }
    const error =
      data && typeof data === "object" && "error" in data
        ? String(data.error)
        : `后端请求失败：${response.status}`;
    throw new Error(error);
  }

  return data as T;
}

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const status = await requestJson<AuthStatus>("/api/auth/status", {
    skipAuthRedirect: true,
  });
  setCsrfToken(status.csrf_token);
  return status;
}

export async function login(payload: LoginPayload): Promise<AuthStatus> {
  const status = await requestJson<AuthStatus>("/api/auth/login", {
    method: "POST",
    body: payload,
    skipAuthRedirect: true,
  });
  setCsrfToken(status.csrf_token);
  return status;
}

export async function logout(): Promise<AuthStatus> {
  const status = await requestJson<AuthStatus>("/api/auth/logout", {
    method: "POST",
    body: {},
    skipAuthRedirect: true,
  });
  setCsrfToken("");
  return status;
}

export async function fetchStatus(): Promise<AppStatus> {
  return requestJson<AppStatus>("/api/status");
}

export async function fetchLogs({
  limit = 100,
}: { limit?: number } = {}): Promise<LogsResponse> {
  return requestJson<LogsResponse>(`/api/logs?limit=${encodeURIComponent(limit)}`);
}

export async function updateTarget(payload: TargetForm): Promise<RuntimeMutationResult> {
  return requestJson<RuntimeMutationResult>("/api/runtime/target", {
    method: "PUT",
    body: payload,
  });
}

export async function addFavoriteLocation(
  payload: FavoriteLocation,
): Promise<RuntimeMutationResult> {
  return requestJson<RuntimeMutationResult>("/api/runtime/favorites", {
    method: "POST",
    body: payload,
  });
}

export async function updateMode(mode: RewriteMode): Promise<RuntimeMutationResult> {
  return requestJson<RuntimeMutationResult>("/api/runtime/mode", {
    method: "PUT",
    body: { mode },
  });
}

export async function updateEnabled(
  enabled: boolean,
): Promise<RuntimeMutationResult> {
  return requestJson<RuntimeMutationResult>("/api/runtime/enabled", {
    method: "PUT",
    body: { enabled },
  });
}

export async function updateProxyEnabled(
  enabled: boolean,
): Promise<RuntimeMutationResult> {
  return requestJson<RuntimeMutationResult>("/api/runtime/proxy-enabled", {
    method: "PUT",
    body: { enabled },
  });
}

export async function resetPreviewState(): Promise<AppStatus> {
  return requestJson<AppStatus>("/api/runtime/reset", {
    method: "POST",
    body: {},
  });
}

export async function generateCa({
  regenerate = false,
}: { regenerate?: boolean } = {}): Promise<GenerateCaResult> {
  return requestJson<GenerateCaResult>("/api/ca/generate", {
    method: "POST",
    body: { regenerate },
  });
}
