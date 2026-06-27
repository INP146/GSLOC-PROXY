import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import type { AppStatus, RuntimeState } from "../src/types";

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
  enabled: true,
  target: {
    lat: 31.230416,
    lng: 121.473701,
    name: '中国上海市黄浦区人民广场',
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
    reject_total: 1,
    patch_success: 12,
    patch_noop: 5,
    patch_error: 0,
  };
  let lastPatch: AppStatus["last_patch"] = {
    patched: 1,
    old_center: [31.22991, 121.47401],
    target: [runtime.target.lat, runtime.target.lng],
    reason: 'dev mock sample',
    sample: ['31.229910,121.474010 → 31.230416,121.473701'],
  };

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
          if (req.method === "GET" && pathname === "/api/status") {
            sendJson(res, snapshotStatus());
            return;
          }

          if (req.method === "GET" && pathname === "/api/metrics") {
            sendJson(res, stats);
            return;
          }

          if (req.method === "PUT" && pathname === "/api/runtime/target") {
            const payload = await readJsonBody(req);
            runtime.target.lat = numberInRange(payload.lat, "lat", -90, 90);
            runtime.target.lng = numberInRange(payload.lng, "lng", -180, 180);
            runtime.target.scale = numberInRange(payload.scale, "scale", 0, 10);
            runtime.target.name = payload.name == null ? "" : String(payload.name);
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
            sendJson(res, {
              ok: true,
              enabled: runtime.enabled,
              runtime: clone(runtime),
            });
            return;
          }

          if (req.method === "POST" && pathname === "/api/runtime/reset") {
            Object.assign(runtime, clone(DEFAULT_RUNTIME));
            lastPatch = null;
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
