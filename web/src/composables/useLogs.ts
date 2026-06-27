import { computed, ref } from "vue";
import { fetchLogs } from "../api";
import type { GslocLogRecord, MessageApi } from "../types";

function getErrorMessage(err: unknown): string | null {
  return err instanceof Error ? err.message : null;
}

export function useLogs(message: MessageApi) {
  const logs = ref<GslocLogRecord[]>([]);
  const logsLoading = ref(false);
  const logsLimit = ref(100);

  const logRows = computed(() =>
    [...logs.value].sort((a, b) => (a.id ?? 0) - (b.id ?? 0)),
  );

  async function refreshLogs({
    silent = false,
    loading = true,
  }: { silent?: boolean; loading?: boolean } = {}) {
    if (loading) logsLoading.value = true;
    try {
      const result = await fetchLogs({ limit: logsLimit.value });
      logs.value = result?.logs || [];
    } catch (err) {
      if (!silent) message.error(getErrorMessage(err) || "读取日志失败");
    } finally {
      if (loading) logsLoading.value = false;
    }
  }

  return {
    logs,
    logsLoading,
    logsLimit,
    logRows,
    refreshLogs,
  };
}
