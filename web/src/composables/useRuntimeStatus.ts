import { computed, reactive, ref } from "vue";
import type { FormInst, SelectOption } from "naive-ui";
import {
  addFavoriteLocation,
  fetchStatus,
  generateCa,
  resetPreviewState,
  updateEnabled,
  updateMode,
  updateProxyEnabled,
  updateTarget,
} from "../api";
import { targetRules } from "../config/runtime";
import {
  formatFavoriteLabel,
  normalizeFavoriteLocation,
} from "../utils/favorites";
import type {
  AppStatus,
  CertificateState,
  FavoriteLocation,
  LastPatch,
  LastPatchRow,
  MessageApi,
  Policy,
  PolicyRule,
  RewriteMode,
  RuntimeState,
  RuntimeTarget,
  Stats,
  TargetForm,
} from "../types";

function getErrorMessage(err: unknown): string | null {
  return err instanceof Error ? err.message : null;
}

function isFavoriteLocation(
  favorite: FavoriteLocation | null,
): favorite is FavoriteLocation {
  return favorite !== null;
}

export function useRuntimeStatus(message: MessageApi) {
  const status = ref<AppStatus | null>(null);
  const loading = ref(true);
  const saving = ref(false);
  const caBusy = ref(false);
  const favoriteLocations = ref<FavoriteLocation[]>([]);
  const selectedFavoriteKey = ref<string | null>(null);
  const formRef = ref<FormInst | null>(null);
  const form = reactive<TargetForm>({
    lat: null,
    lng: null,
    name: "",
    scale: 1,
  });

  const runtime = computed<RuntimeState>(() => status.value?.runtime || {});
  const target = computed<RuntimeTarget>(() => runtime.value.target || {});
  const policy = computed<Policy>(() => status.value?.policy || {});
  const stats = computed<Stats>(() => status.value?.stats || {});
  const allowRules = computed<PolicyRule[]>(() => policy.value.allow || []);
  const lastPatch = computed<LastPatch | null>(
    () => status.value?.last_patch || null,
  );
  const ca = computed<CertificateState>(() => status.value?.ca || {});
  const caUrl = computed(() => ca.value.url || "/ca.cer");
  const favoriteOptions = computed<SelectOption[]>(() =>
    favoriteLocations.value.map((favorite) => ({
      label: formatFavoriteLabel(favorite),
      value: favorite.key,
    })),
  );
  const canFavoriteCurrentTarget = computed(() => {
    const lat = Number(form.lat);
    const lng = Number(form.lng);
    return Number.isFinite(lat) && Number.isFinite(lng);
  });
  const lastPatchRows = computed<LastPatchRow[]>(() => {
    if (!lastPatch.value) return [];
    return [
      { label: "patched", value: lastPatch.value.patched ?? "-" },
      {
        label: "old_center",
        value: lastPatch.value.old_center?.join(", ") || "-",
      },
      { label: "target", value: lastPatch.value.target?.join(", ") || "-" },
      { label: "reason", value: lastPatch.value.reason || "-" },
    ];
  });

  function syncFavoriteLocations(nextRuntime: RuntimeState = runtime.value) {
    const nextFavorites = (nextRuntime?.favorites || [])
      .map(normalizeFavoriteLocation)
      .filter(isFavoriteLocation);
    favoriteLocations.value = Array.from(
      new Map(nextFavorites.map((favorite) => [favorite.key, favorite])).values(),
    );
  }

  function fillForm(nextStatus: AppStatus) {
    const nextTarget = nextStatus?.runtime?.target || {};
    form.lat = Number(nextTarget.lat ?? 31.230416);
    form.lng = Number(nextTarget.lng ?? 121.473701);
    form.name = nextTarget.name ?? "";
    form.scale = Number(nextTarget.scale ?? 1);
  }

  async function refresh({
    quiet = false,
    silent = false,
  }: { quiet?: boolean; silent?: boolean } = {}) {
    if (!quiet) loading.value = true;
    try {
      const nextStatus = await fetchStatus();
      status.value = nextStatus;
      syncFavoriteLocations(nextStatus.runtime);
      if (!quiet) fillForm(nextStatus);
    } catch (err) {
      if (!silent) message.error(getErrorMessage(err) || "读取状态失败");
    } finally {
      loading.value = false;
    }
  }

  async function saveTarget() {
    try {
      await formRef.value?.validate();
    } catch {
      return;
    }

    saving.value = true;
    try {
      await updateTarget({ ...form });
      await refresh({ quiet: true });
      message.success("模拟上游位置已保存");
    } catch (err) {
      message.error(getErrorMessage(err) || "保存模拟上游位置失败");
    } finally {
      saving.value = false;
    }
  }

  async function changeMode(mode: RewriteMode) {
    saving.value = true;
    try {
      await updateMode(mode);
      await refresh({ quiet: true });
      message.success(`已切换到 ${mode}`);
    } catch (err) {
      message.error(getErrorMessage(err) || "切换模式失败");
    } finally {
      saving.value = false;
    }
  }

  async function toggleEnabled() {
    saving.value = true;
    try {
      await updateEnabled(!runtime.value.enabled);
      await refresh({ quiet: true });
      message.success(runtime.value.enabled ? "已开启实验" : "已终止实验");
    } catch (err) {
      message.error(getErrorMessage(err) || "切换实验失败");
    } finally {
      saving.value = false;
    }
  }

  async function toggleProxyEnabled() {
    saving.value = true;
    try {
      await updateProxyEnabled(!runtime.value.proxy_enabled);
      await refresh({ quiet: true });
      message.success(runtime.value.proxy_enabled ? "已开启代理会话" : "已关闭代理会话");
    } catch (err) {
      message.error(getErrorMessage(err) || "切换代理开关失败");
    } finally {
      saving.value = false;
    }
  }

  async function resetState() {
    saving.value = true;
    try {
      status.value = await resetPreviewState();
      syncFavoriteLocations(status.value.runtime);
      fillForm(status.value);
      message.success("已恢复默认运行时状态");
    } catch (err) {
      message.error(getErrorMessage(err) || "恢复默认运行时状态失败");
    } finally {
      saving.value = false;
    }
  }

  async function favoriteCurrentTarget() {
    const favorite = normalizeFavoriteLocation(form);
    if (!favorite) {
      message.warning("请先填写有效的经纬度");
      return;
    }
    try {
      const result = await addFavoriteLocation(favorite);
      if (result?.runtime) {
        status.value = { ...status.value, runtime: result.runtime };
        syncFavoriteLocations(result.runtime);
      }
      selectedFavoriteKey.value = favorite.key;
      message.success("已收藏地址");
    } catch (err) {
      message.error(getErrorMessage(err) || "收藏地址失败");
    }
  }

  function applyFavoriteLocation(key: string | null) {
    selectedFavoriteKey.value = key;
    const favorite = favoriteLocations.value.find((item) => item.key === key);
    if (!favorite) return;
    form.name = favorite.name;
    form.lat = favorite.lat;
    form.lng = favorite.lng;
    form.scale = favorite.scale;
  }

  async function handleGenerateCa() {
    caBusy.value = true;
    const hadCa = Boolean(ca.value.available);
    try {
      const result = await generateCa({ regenerate: hadCa });
      if (result?.restart_required) {
        message.success(
          hadCa
            ? "CA 证书已重新生成，代理正在重启"
            : "CA 证书已生成，代理正在重启",
        );
        window.setTimeout(() => refresh({ quiet: true, silent: true }), 2500);
      } else {
        await refresh({ quiet: true });
        message.success("CA 证书已存在");
      }
    } catch (err) {
      message.error(getErrorMessage(err) || "生成 CA 证书失败");
    } finally {
      caBusy.value = false;
    }
  }

  return {
    status,
    loading,
    saving,
    caBusy,
    formRef,
    form,
    runtime,
    target,
    policy,
    stats,
    allowRules,
    lastPatch,
    ca,
    caUrl,
    favoriteOptions,
    selectedFavoriteKey,
    canFavoriteCurrentTarget,
    lastPatchRows,
    rules: targetRules,
    refresh,
    saveTarget,
    changeMode,
    toggleEnabled,
    toggleProxyEnabled,
    resetState,
    favoriteCurrentTarget,
    applyFavoriteLocation,
    handleGenerateCa,
  };
}
