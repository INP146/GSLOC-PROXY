import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import type { AppStatus, GslocLogRecord, RuntimeState } from "../src/types";

type MockRuntime = RuntimeState & {
  enabled: boolean;
  target: {
    lat: number;
    lng: number;
    name: string;
    mode: string;
    scale: number;
  };
};

const DEFAULT_RUNTIME: MockRuntime = {
  proxy_enabled: true,
  session_id: 1,
  session_started_at: Date.now() / 1000,
  enabled: true,
  target: {
    lat: 0.0,
    lng: 0.0,
    name: 'Authorized Test Location',
    mode: 'clamp',
    scale: 1,
  },
};

const DEFAULT_POLICY = {
  allow: [
    {
      host: 'gs-loc-cn.apple.com',
      paths: ['/clls/wloc'],
      pass_through_other_paths: true,
    },
    {
      host: 'gs-loc.apple.com',
      paths: ['/clls/wloc'],
      pass_through_other_paths: true,
    },
  ],
  failure: {
    patch_error: 'pass_through',
  },
  logging: {
    sample_limit: 5,
  },
};

const DEV_AUTH = {
  username: "admin",
  password: "admin",
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function sendJson(res: ServerResponse, payload: unknown, status = 200): void {
  const body = JSON.stringify(payload);
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Content-Length", Buffer.byteLength(body));
  res.setHeader("Cache-Control", "no-store");
  res.end(body);
}

function sendError(res: ServerResponse, error: string, status = 400): void {
  sendJson(res, { ok: false, error }, status);
}

function getCookie(req: IncomingMessage, name: string): string {
  const header = req.headers.cookie || "";
  const cookies = Object.fromEntries(
    header
      .split(";")
      .map((part) => part.trim().split("="))
      .filter((parts) => parts.length === 2),
  );
  return cookies[name] || "";
}

function readJsonBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let length = 0;

    req.on("data", (chunk: Buffer) => {
      length += chunk.length;
      if (length > 1024 * 1024) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });

    req.on("end", () => {
      if (!chunks.length) {
        resolve({});
        return;
      }

      try {
        const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          reject(new Error("JSON body must be an object"));
          return;
        }
        resolve(payload as Record<string, unknown>);
      } catch {
        reject(new Error("invalid JSON body"));
      }
    });

    req.on("error", reject);
  });
}

function numberInRange(
  value: unknown,
  name: string,
  min: number,
  max: number,
): number {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error(`${name} must be a number`);
  }
  if (number < min || number > max) {
    throw new Error(`${name} must be between ${min} and ${max}`);
  }
  return number;
}

function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "mock backend error";
}

export function mockBackendPlugin(): Plugin {
  const runtime = clone(DEFAULT_RUNTIME);
  const policy = clone(DEFAULT_POLICY);
  const stats = {
    request_total: 18,
    pass_through_total: 0,
    reject_total: 1,
    patch_success: 12,
    patch_noop: 5,
    patch_error: 0,
  };
  let lastPatch: AppStatus["last_patch"] = {
    patched: 1,
    old_center: [0.0001, -0.0001],
    target: [runtime.target.lat, runtime.target.lng],
    reason: 'dev mock sample',
    sample: ['0.000100,-0.000100 → 0.000000,0.000000'],
  };
  let sessionToken = "";
  let csrfToken = "";
  let nextLogId = 1;
  const logs: GslocLogRecord[] = [];

  function recordLog(
    type: string,
    level: GslocLogRecord["level"],
    message: string,
    extra: Partial<GslocLogRecord> = {},
  ): void {
    logs.push({
      id: nextLogId++,
      ts: Date.now() / 1000,
      session_id: runtime.session_id,
      logger: "gsloc-proxy",
      type,
      level,
      message,
      ...extra,
    });
    if (logs.length > 1000) logs.splice(0, logs.length - 1000);
  }

  recordLog("mock_started", "info", "mock gsloc-proxy backend started", {
    layer: "management",
    source: "web.dev.mockBackend",
  });

  function snapshotStatus(): AppStatus {
    return {
      runtime: clone(runtime),
      policy: clone(policy),
      stats: { ...stats },
      last_patch: lastPatch ? clone(lastPatch) : null,
      ca: {
        available: false,
        url: '/ca.cer',
      },
      logs: {
        count: logs.length,
        latest_id: logs.length ? logs[logs.length - 1].id : null,
        level: "info",
        terminal_level: "info",
      },
      web: {
        mode: 'mock',
      },
    };
  }

  return {
    name: "gsloc-mock-backend",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const pathname = new URL(req.url || "/", "http://localhost").pathname;

        if (pathname === "/ca.cer") {
          res.statusCode = 404;
          res.end("CA certificate not available in dev mock");
          return;
        }

        if (!pathname.startsWith("/api")) {
          next();
          return;
        }

        try {
          if (req.method === "GET" && pathname === "/api/auth/status") {
            const authenticated = Boolean(sessionToken && getCookie(req, "gsloc_session") === sessionToken);
            sendJson(res, {
              auth_required: true,
              authenticated,
              user: authenticated ? DEV_AUTH.username : null,
              csrf_token: authenticated ? csrfToken : undefined,
            });
            return;
          }

          if (req.method === "POST" && pathname === "/api/auth/login") {
            const payload = await readJsonBody(req);
            if (payload.username !== DEV_AUTH.username || payload.password !== DEV_AUTH.password) {
              sendError(res, "invalid username or password", 401);
              return;
            }
            sessionToken = "dev-session";
            csrfToken = "dev-csrf";
            res.setHeader("Set-Cookie", "gsloc_session=dev-session; Path=/; HttpOnly; SameSite=Strict");
            sendJson(res, {
              ok: true,
              auth_required: true,
              authenticated: true,
              user: DEV_AUTH.username,
              csrf_token: csrfToken,
            });
            return;
          }

          if (req.method === "POST" && pathname === "/api/auth/logout") {
            sessionToken = "";
            csrfToken = "";
            res.setHeader("Set-Cookie", "gsloc_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict");
            sendJson(res, {
              ok: true,
              auth_required: true,
              authenticated: false,
              user: null,
            });
            return;
          }

          if (!sessionToken || getCookie(req, "gsloc_session") !== sessionToken) {
            sendError(res, "unauthorized", 401);
            return;
          }

          if (
            req.method !== "GET" &&
            req.headers["x-csrf-token"] !== csrfToken
          ) {
            sendError(res, "invalid csrf token", 403);
            return;
          }

          if (req.method === "GET" && pathname === "/api/status") {
            sendJson(res, snapshotStatus());
            return;
          }

          if (req.method === "GET" && pathname === "/api/metrics") {
            sendJson(res, stats);
            return;
          }

          if (req.method === "GET" && pathname === "/api/logs") {
            const limit = Math.max(1, Math.min(Number(new URL(req.url || "/", "http://localhost").searchParams.get("limit") || 100), 1000));
            const rows = logs.slice(-limit);
            sendJson(res, {
              logs: clone(rows),
              count: rows.length,
              limit,
              level: "info",
            });
            return;
          }

          if (req.method === "PUT" && pathname === "/api/runtime/target") {
            const payload = await readJsonBody(req);
            runtime.target.lat = numberInRange(payload.lat, "lat", -90, 90);
            runtime.target.lng = numberInRange(payload.lng, "lng", -180, 180);
            runtime.target.scale = numberInRange(payload.scale, "scale", 0, 10);
            runtime.target.name = payload.name == null ? "" : String(payload.name);
            recordLog("runtime_target_updated", "info", "target updated", {
              layer: "runtime",
              source: "mock.runtime",
              details: {
                target: clone(runtime.target),
              },
            });
            lastPatch = {
              patched: 1,
              old_center: lastPatch?.target || [31.22991, 121.47401],
              target: [runtime.target.lat, runtime.target.lng],
              reason: "dev mock target updated",
              sample: [`mock → ${runtime.target.lat},${runtime.target.lng}`],
            };
            sendJson(res, {
              ok: true,
              target: clone(runtime.target),
              runtime: clone(runtime),
            });
            return;
          }

          if (req.method === "PUT" && pathname === "/api/runtime/mode") {
            const payload = await readJsonBody(req);
            const mode = String(payload.mode);
            if (!["clamp", "shift"].includes(mode)) {
              sendError(res, "mode must be clamp or shift");
              return;
            }
            runtime.target.mode = mode;
            recordLog("runtime_mode_updated", "info", "mode updated", {
              layer: "runtime",
              source: "mock.runtime",
              details: { mode },
            });
            sendJson(res, {
              ok: true,
              target: clone(runtime.target),
              runtime: clone(runtime),
            });
            return;
          }

          if (req.method === "PUT" && pathname === "/api/runtime/enabled") {
            const payload = await readJsonBody(req);
            if (typeof payload.enabled !== "boolean") {
              sendError(res, "enabled must be boolean");
              return;
            }
            runtime.enabled = payload.enabled;
            recordLog("runtime_enabled_updated", "info", "runtime enabled updated", {
              layer: "runtime",
              source: "mock.runtime",
              details: { enabled: runtime.enabled },
            });
            sendJson(res, {
              ok: true,
              enabled: runtime.enabled,
              runtime: clone(runtime),
            });
            return;
          }

          if (req.method === "PUT" && pathname === "/api/runtime/proxy-enabled") {
            const payload = await readJsonBody(req);
            if (typeof payload.enabled !== "boolean") {
              sendError(res, "enabled must be boolean");
              return;
            }
            const wasEnabled = Boolean(runtime.proxy_enabled);
            runtime.proxy_enabled = payload.enabled;
            if (!wasEnabled && runtime.proxy_enabled) {
              runtime.session_id = Number(runtime.session_id || 1) + 1;
              runtime.session_started_at = Date.now() / 1000;
              stats.request_total = 0;
              stats.pass_through_total = 0;
              stats.reject_total = 0;
              stats.patch_success = 0;
              stats.patch_noop = 0;
              stats.patch_error = 0;
              lastPatch = null;
              logs.length = 0;
              nextLogId = 1;
            }
            recordLog(runtime.proxy_enabled ? "proxy_session_started" : "proxy_session_stopped", runtime.proxy_enabled ? "success" : "warning", runtime.proxy_enabled ? "proxy session started" : "proxy session stopped", {
              layer: "runtime",
              source: "mock.runtime",
            });
            sendJson(res, {
              ok: true,
              proxy_enabled: runtime.proxy_enabled,
              runtime: clone(runtime),
            });
            return;
          }

          if (req.method === "POST" && pathname === "/api/runtime/reset") {
            Object.assign(runtime, clone(DEFAULT_RUNTIME));
            lastPatch = null;
            recordLog("runtime_reset", "warning", "runtime state reset", {
              layer: "runtime",
              source: "mock.runtime",
            });
            sendJson(res, snapshotStatus());
            return;
          }

          sendError(res, "not found", 404);
        } catch (err) {
          sendError(res, getErrorMessage(err));
        }
      });
    },
  };
}
