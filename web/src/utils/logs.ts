import type { GslocLogRecord } from "../types";
import { formatTimestamp } from "./format";

interface TerminalToken {
  text: string;
  class?: string;
}

function formatLogTimestamp(ts?: number): string {
  return ts ? formatTimestamp(ts) : "----/--/-- --:--:--";
}

function compactDetails(details?: Record<string, unknown>): string {
  if (!details) return "";
  const parts = [];
  for (const [key, value] of Object.entries(details)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value) || typeof value === "object") {
      parts.push(`${key}=${JSON.stringify(value)}`);
    } else {
      parts.push(`${key}=${value}`);
    }
  }
  return parts.join(" ");
}

function terminalLevelClass(level?: string): string {
  if (level === "success") return "terminal-token-success";
  if (level === "warning") return "terminal-token-warning";
  if (level === "error") return "terminal-token-error";
  return "terminal-token-info";
}

export function terminalLogTokens(event: GslocLogRecord): TerminalToken[] {
  const tokens: TerminalToken[] = [
    { text: formatLogTimestamp(event.ts), class: "terminal-token-time" },
    { text: " " },
    {
      text: (event.level || "info").toUpperCase().padEnd(7, " "),
      class: terminalLevelClass(event.level),
    },
    { text: " " },
    {
      text: `${event.logger || "gsloc-proxy"}[${event.layer || "system"}]`,
      class: "terminal-token-layer",
    },
  ];

  if (event.session_id) {
    tokens.push(
      { text: " " },
      { text: `session=${event.session_id}`, class: "terminal-token-source" },
    );
  }

  if (event.source) {
    tokens.push(
      { text: " " },
      { text: event.source, class: "terminal-token-source" },
    );
  }

  if (event.method || event.host || event.path) {
    tokens.push({ text: " - " });
    if (event.method) {
      tokens.push(
        { text: event.method, class: "terminal-token-method" },
        { text: " " },
      );
    }
    if (event.host) {
      tokens.push(
        { text: event.host, class: "terminal-token-host" },
        { text: " " },
      );
    }
    if (event.path) {
      tokens.push({ text: event.path, class: "terminal-token-path" });
    }
  }

  if (event.status) {
    tokens.push(
      { text: " " },
      { text: `status=${event.status}`, class: "terminal-token-status" },
    );
  }
  if (event.client) {
    tokens.push(
      { text: " " },
      { text: `client=${event.client}`, class: "terminal-token-client" },
    );
  }

  tokens.push(
    { text: " - " },
    { text: `${event.type}:`, class: "terminal-token-type" },
    { text: " " },
    { text: event.message || "", class: "terminal-token-message" },
  );

  const details = compactDetails(event.details);
  if (details) {
    tokens.push(
      { text: " " },
      { text: details, class: "terminal-token-details" },
    );
  }

  return tokens;
}
