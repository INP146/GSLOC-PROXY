<script setup lang="ts">
import { NIcon } from "naive-ui";
import { DocumentTextOutline, RefreshOutline } from "@vicons/ionicons5";
import { terminalLogTokens } from "../utils/logs";
import type { GslocLogRecord } from "../types";

withDefaults(
  defineProps<{
    logRows?: GslocLogRecord[];
    logsLoading?: boolean;
  }>(),
  {
    logRows: () => [],
    logsLoading: false,
  },
);

defineEmits<{
  refresh: [];
}>();
</script>

<template>
  <n-card size="small" class="panel-card logs-card" :segmented="{ content: true }">
    <template #header>
      <div class="card-title">
        <n-icon :component="DocumentTextOutline" />
        <span>日志</span>
      </div>
    </template>
    <template #header-extra>
      <n-button size="small" secondary :loading="logsLoading" @click="$emit('refresh')">
        <template #icon>
          <n-icon :component="RefreshOutline" />
        </template>
        刷新
      </n-button>
    </template>

    <n-spin :show="logsLoading">
      <n-empty v-if="!logRows.length" description="暂无日志" class="logs-empty" />
      <pre v-else class="terminal-log"><code><span
        v-for="event in logRows"
        :key="event.id"
        class="terminal-log-line"
      ><span
        v-for="(token, index) in terminalLogTokens(event)"
        :key="index"
        :class="token.class"
      >{{ token.text }}</span>
</span></code></pre>
    </n-spin>
  </n-card>
</template>
