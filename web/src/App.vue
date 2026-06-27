<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import type { FormInst } from "naive-ui";
import { createDiscreteApi, NIcon } from "naive-ui";
import { LogoGithub } from "@vicons/ionicons5";
import { fetchAuthStatus, login, logout, onAuthChanged } from "./api";
import AppHeader from "./components/AppHeader.vue";
import DashboardView from "./components/DashboardView.vue";
import LoginView from "./components/LoginView.vue";
import LogsView from "./components/LogsView.vue";
import MapPickerModal from "./components/MapPickerModal.vue";
import { useLogs } from "./composables/useLogs";
import { useMapPicker } from "./composables/useMapPicker";
import { useRuntimeStatus } from "./composables/useRuntimeStatus";
import { themeOverrides } from "./theme";
import type { AuthStatus, LoginPayload } from "./types";

const { message } = createDiscreteApi(["message"]);
const activeTab = ref("dashboard");
const auth = ref<AuthStatus | null>(null);
const authChecking = ref(true);
const loginLoading = ref(false);
const loginError = ref("");
const repositoryUrl = "https://github.com/INP146/GSLOC-PROXY";
const copyrightNotice = "Copyright (c) 2026 @INP146";
let refreshTimer: number | null = null;
let removeAuthListener: (() => void) | null = null;

const runtimeState = useRuntimeStatus(message);
const logsState = useLogs(message);
const mapPicker = useMapPicker({
  form: runtimeState.form,
  message,
});

const {
  status,
  loading,
  saving,
  caBusy,
  formRef,
  form,
  runtime,
  target,
  stats,
  allowRules,
  lastPatch,
  ca,
  caUrl,
  favoriteOptions,
  selectedFavoriteKey,
  isCurrentTargetFavorited,
  canFavoriteCurrentTarget,
  lastPatchRows,
  rules,
  refresh,
  saveTarget,
  changeMode,
  toggleEnabled,
  toggleProxyEnabled,
  resetState,
  toggleFavoriteCurrentTarget,
  applyFavoriteLocation,
  handleGenerateCa,
} = runtimeState;

const { logsLoading, logRows, refreshLogs } = logsState;

const {
  mapPickerVisible,
  mapContainerRef,
  pickedLatLng,
  placeSearch,
  searchPlaces,
  applySearchResult,
  closePlaceSearchResults,
  openMapPicker,
  applyPickedLocation,
  closeMapPicker,
  cleanupPickerMap,
} = mapPicker;

async function changeTab(name: string) {
  activeTab.value = name;
  if (name === "logs") await refreshLogs({ silent: true });
}

function refreshActiveTab() {
  if (activeTab.value === "logs") return refreshLogs();
  return refresh();
}

function isAuthenticated(nextAuth: AuthStatus | null = auth.value) {
  return (
    Boolean(nextAuth) &&
    (!nextAuth?.auth_required || Boolean(nextAuth?.authenticated))
  );
}

function stopRefreshTimer() {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function startRefreshTimer() {
  stopRefreshTimer();
  refreshTimer = window.setInterval(() => {
    refresh({ quiet: true, silent: true });
    if (activeTab.value === "logs")
      refreshLogs({ silent: true, loading: false });
  }, 1000);
}

async function bootstrapConsole() {
  await refresh();
  startRefreshTimer();
}

async function checkAuth() {
  authChecking.value = true;
  loginError.value = "";
  stopRefreshTimer();
  try {
    const nextAuth = await fetchAuthStatus();
    auth.value = nextAuth;
    if (isAuthenticated(nextAuth)) {
      await bootstrapConsole();
    }
  } catch (err) {
    loginError.value = err instanceof Error ? err.message : "读取登录状态失败";
  } finally {
    authChecking.value = false;
  }
}

async function handleLogin(payload: LoginPayload) {
  loginLoading.value = true;
  loginError.value = "";
  try {
    auth.value = await login(payload);
    await bootstrapConsole();
    message.success("登录成功");
  } catch (err) {
    loginError.value = err instanceof Error ? err.message : "登录失败";
  } finally {
    loginLoading.value = false;
  }
}

async function handleLogout() {
  try {
    await logout();
  } catch {
    // The local session is discarded even if the server is already gone.
  }
  stopRefreshTimer();
  try {
    auth.value = await fetchAuthStatus();
  } catch {
    auth.value = { auth_required: true, authenticated: false };
  }
}

function setMapPickerVisible(value: boolean) {
  mapPickerVisible.value = value;
}

function setFormRef(value: FormInst | null) {
  formRef.value = value;
}

function setMapContainerRef(value: HTMLElement | null) {
  mapContainerRef.value = value;
}

onMounted(() => {
  removeAuthListener = onAuthChanged(() => {
    stopRefreshTimer();
    auth.value = { auth_required: true, authenticated: false };
    message.warning("登录已失效，请重新登录");
  });
  checkAuth();
});

onUnmounted(() => {
  stopRefreshTimer();
  removeAuthListener?.();
  cleanupPickerMap();
});
</script>

<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <div v-if="authChecking" class="auth-loading">
      <n-spin size="large" />
    </div>

    <div v-else-if="!isAuthenticated()" class="login-page">
      <LoginView
        :loading="loginLoading"
        :error="loginError"
        @login="handleLogin"
      />
      <footer class="app-footer">
        <a :href="repositoryUrl" target="_blank" rel="noopener noreferrer">
          <n-icon :component="LogoGithub" />
          <span>GSLOC-PROXY</span>
        </a>
        <span class="footer-divider">|</span>
        <span>{{ copyrightNotice }}</span>
      </footer>
    </div>

    <n-layout v-else class="app-layout">
      <AppHeader
        :active-tab="activeTab"
        :logs-loading="logsLoading"
        :loading="loading"
        :saving="saving"
        :status="status"
        :runtime="runtime"
        :user="auth?.user"
        :auth-required="auth?.auth_required"
        @refresh="refreshActiveTab"
        @toggle-proxy-enabled="toggleProxyEnabled"
        @toggle-enabled="toggleEnabled"
        @logout="handleLogout"
      />

      <div class="app-tabs">
        <n-tabs
          :value="activeTab"
          type="line"
          animated
          @update:value="changeTab"
        >
          <n-tab name="dashboard">状态面板</n-tab>
          <n-tab name="logs">日志</n-tab>
        </n-tabs>
      </div>

      <n-layout-content class="app-content">
        <DashboardView
          v-if="activeTab === 'dashboard'"
          :status="status"
          :loading="loading"
          :saving="saving"
          :ca-busy="caBusy"
          :form="form"
          :rules="rules"
          :stats="stats"
          :target="target"
          :allow-rules="allowRules"
          :last-patch="lastPatch"
          :last-patch-rows="lastPatchRows"
          :ca="ca"
          :ca-url="caUrl"
          :favorite-options="favoriteOptions"
          :selected-favorite-key="selectedFavoriteKey"
          :is-current-target-favorited="isCurrentTargetFavorited"
          :can-favorite-current-target="canFavoriteCurrentTarget"
          @form-ref="setFormRef"
          @reset-state="resetState"
          @apply-favorite="applyFavoriteLocation"
          @toggle-favorite-current="toggleFavoriteCurrentTarget"
          @open-map-picker="openMapPicker"
          @save-target="saveTarget"
          @change-mode="changeMode"
          @generate-ca="handleGenerateCa"
        />

        <LogsView
          v-else-if="activeTab === 'logs'"
          :log-rows="logRows"
          :logs-loading="logsLoading"
          @refresh="refreshLogs()"
        />
      </n-layout-content>

      <n-layout-footer class="app-footer">
        <a :href="repositoryUrl" target="_blank" rel="noopener noreferrer">
          <n-icon :component="LogoGithub" />
          <span>GSLOC-PROXY</span>
        </a>
        <span class="footer-divider">|</span>
        <span>{{ copyrightNotice }}</span>
      </n-layout-footer>
    </n-layout>

    <MapPickerModal
      v-if="isAuthenticated()"
      :show="mapPickerVisible"
      :place-search="placeSearch"
      :picked-lat-lng="pickedLatLng"
      @update:show="setMapPickerVisible"
      @map-ref="setMapContainerRef"
      @after-leave="cleanupPickerMap"
      @close-results="closePlaceSearchResults"
      @search="searchPlaces"
      @apply-search-result="applySearchResult"
      @close="closeMapPicker"
      @apply-picked="applyPickedLocation"
    />
  </n-config-provider>
</template>
