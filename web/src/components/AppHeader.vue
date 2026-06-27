<script setup lang="ts">
import { NIcon } from "naive-ui";
import { LogoGithub, PowerOutline, RefreshOutline } from "@vicons/ionicons5";
import type { AppStatus, RuntimeState } from "../types";

withDefaults(
  defineProps<{
    activeTab: string;
    logsLoading?: boolean;
    loading?: boolean;
    saving?: boolean;
    status?: AppStatus | null;
    runtime: RuntimeState;
  }>(),
  {
    logsLoading: false,
    loading: false,
    saving: false,
    status: null,
  },
);

defineEmits<{
  refresh: [];
  "toggle-enabled": [];
}>();
</script>

<template>
  <n-layout-header bordered class="app-header">
    <div class="header-main">
      <a
        class="brand-mark"
        href="https://github.com/INP146/GSLOC-PROXY"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Open GSLOC-PROXY on GitHub"
      >
        <n-icon :component="LogoGithub" />
      </a>
    </div>
    <n-space class="header-actions" align="center" :size="10">
      <n-button
        secondary
        :loading="activeTab === 'logs' ? logsLoading : loading"
        @click="$emit('refresh')"
      >
        <template #icon>
          <n-icon :component="RefreshOutline" />
        </template>
        刷新
      </n-button>
      <n-button
        type="primary"
        :loading="saving"
        :disabled="loading || !status"
        @click="$emit('toggle-enabled')"
      >
        <template #icon>
          <n-icon :component="PowerOutline" />
        </template>
        {{ runtime.enabled ? "终止实验" : "开始实验" }}
      </n-button>
    </n-space>
  </n-layout-header>
</template>
