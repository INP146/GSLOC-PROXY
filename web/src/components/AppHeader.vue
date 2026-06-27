<script setup lang="ts">
import { computed } from "vue";
import { NIcon } from "naive-ui";
import {
  LogOutOutline,
  LogoGithub,
  PowerOutline,
  RefreshOutline,
} from "@vicons/ionicons5";
import type { AppStatus, RuntimeState } from "../types";

const props = withDefaults(
  defineProps<{
    activeTab: string;
    logsLoading?: boolean;
    loading?: boolean;
    saving?: boolean;
    status?: AppStatus | null;
    runtime: RuntimeState;
    user?: string | null;
    authRequired?: boolean;
  }>(),
  {
    logsLoading: false,
    loading: false,
    saving: false,
    status: null,
    user: null,
    authRequired: false,
  },
);

defineEmits<{
  refresh: [];
  "toggle-proxy-enabled": [];
  "toggle-enabled": [];
  logout: [];
}>();

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(remainingSeconds)}`;
}

const proxyButtonLabel = computed(() => {
  if (!props.runtime.proxy_enabled) return "开启代理";
  const startedAt = Number(props.runtime.session_started_at);
  if (!Number.isFinite(startedAt)) return "00:00:00";
  return formatDuration(Date.now() / 1000 - startedAt);
});
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
      <h1 class="brand-title">GSLOC-PROXY</h1>
    </div>
    <n-space class="header-actions" align="center" :size="10">
      <n-button
        :type="runtime.proxy_enabled ? 'warning' : 'primary'"
        :loading="saving"
        :disabled="loading || !status"
        @click="$emit('toggle-proxy-enabled')"
      >
        <template #icon>
          <n-icon :component="PowerOutline" />
        </template>
        {{ proxyButtonLabel }}
      </n-button>
      <n-button
        :type="runtime.enabled ? 'warning' : 'primary'"
        secondary
        :loading="saving"
        :disabled="loading || !status || !runtime.proxy_enabled"
        @click="$emit('toggle-enabled')"
      >
        <template #icon>
          <n-icon :component="PowerOutline" />
        </template>
        {{ runtime.enabled ? "终止实验" : "开启实验" }}
      </n-button>
      <n-button
        class="header-icon-button"
        secondary
        aria-label="刷新"
        :loading="activeTab === 'logs' ? logsLoading : loading"
        @click="$emit('refresh')"
      >
        <template #icon>
          <n-icon :component="RefreshOutline" />
        </template>
      </n-button>
      <n-button
        type="warning"
        class="header-icon-button"
        v-if="authRequired"
        secondary
        aria-label="退出登录"
        @click="$emit('logout')"
      >
        <template #icon>
          <n-icon :component="LogOutOutline" />
        </template>
      </n-button>
    </n-space>
  </n-layout-header>
</template>
