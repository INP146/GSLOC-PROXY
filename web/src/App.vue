<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import type { FormInst } from "naive-ui";
import { createDiscreteApi } from "naive-ui";
import AppHeader from "./components/AppHeader.vue";
import DashboardView from "./components/DashboardView.vue";
import LogsView from "./components/LogsView.vue";
import MapPickerModal from "./components/MapPickerModal.vue";
import { useLogs } from "./composables/useLogs";
import { useMapPicker } from "./composables/useMapPicker";
import { useRuntimeStatus } from "./composables/useRuntimeStatus";
import { themeOverrides } from "./theme";

const { message } = createDiscreteApi(["message"]);
const activeTab = ref("dashboard");
let refreshTimer: number | null = null;

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
  canFavoriteCurrentTarget,
  lastPatchRows,
  rules,
  refresh,
  saveTarget,
  changeMode,
  toggleEnabled,
  resetState,
  favoriteCurrentTarget,
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
  refresh();
  refreshTimer = window.setInterval(() => {
    refresh({ quiet: true, silent: true });
    if (activeTab.value === "logs") refreshLogs({ silent: true });
  }, 5000);
});

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  cleanupPickerMap();
});
</script>

<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-layout class="app-layout">
      <AppHeader
        :active-tab="activeTab"
        :logs-loading="logsLoading"
        :loading="loading"
        :saving="saving"
        :status="status"
        :runtime="runtime"
        @refresh="refreshActiveTab"
        @toggle-enabled="toggleEnabled"
      />

      <div class="app-tabs">
        <n-tabs :value="activeTab" type="line" animated @update:value="changeTab">
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
          :can-favorite-current-target="canFavoriteCurrentTarget"
          @form-ref="setFormRef"
          @reset-state="resetState"
          @apply-favorite="applyFavoriteLocation"
          @favorite-current="favoriteCurrentTarget"
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
    </n-layout>

    <MapPickerModal
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
