import type { LogEvent } from "../types";

interface TerminalToken {
  text: string;
  class?: string;
}

function formatEventTimestamp(ts?: number): string {
  if (!ts) return "----/--/-- --:--:--";
  const date = new Date(ts * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
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

export function terminalLogTokens(event: LogEvent): TerminalToken[] {
  const tokens: TerminalToken[] = [
    { text: formatEventTimestamp(event.ts), class: "terminal-token-time" },
    { text: " " },
    {
      text: (event.level || "info").toUpperCase().padEnd(7, " "),
      class: terminalLevelClass(event.level),
    },
    { text: " " },
    { text: `[${event.layer || "system"}]`, class: "terminal-token-layer" },
  ];

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
