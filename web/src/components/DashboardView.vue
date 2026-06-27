<script setup lang="ts">
import { computed } from "vue";
import type { FormInst, FormRules, SelectOption } from "naive-ui";
import { NIcon } from "naive-ui";
import {
  DocumentTextOutline,
  DownloadOutline,
  LocationOutline,
  OptionsOutline,
  PowerOutline,
  RadioButtonOnOutline,
  RefreshOutline,
  ShieldCheckmarkOutline,
  StatsChartOutline,
} from "@vicons/ionicons5";
import { modeOptions } from "../config/runtime";
import type {
  AppStatus,
  CertificateState,
  LastPatch,
  LastPatchRow,
  MetricItem,
  PolicyRule,
  RewriteMode,
  RuntimeTarget,
  Stats,
  TargetForm,
} from "../types";

const props = withDefaults(
  defineProps<{
    status?: AppStatus | null;
    loading?: boolean;
    saving?: boolean;
    caBusy?: boolean;
    form: TargetForm;
    rules: FormRules;
    stats: Stats;
    target: RuntimeTarget;
    allowRules?: PolicyRule[];
    lastPatch?: LastPatch | null;
    lastPatchRows?: LastPatchRow[];
    ca: CertificateState;
    caUrl: string;
    favoriteOptions?: SelectOption[];
    selectedFavoriteKey?: string | null;
    canFavoriteCurrentTarget?: boolean;
  }>(),
  {
    status: null,
    loading: false,
    saving: false,
    caBusy: false,
    allowRules: () => [],
    lastPatch: null,
    lastPatchRows: () => [],
    favoriteOptions: () => [],
    selectedFavoriteKey: null,
    canFavoriteCurrentTarget: false,
  },
);

const emit = defineEmits<{
  "form-ref": [value: FormInst | null];
  "reset-state": [];
  "apply-favorite": [key: string | null];
  "favorite-current": [];
  "open-map-picker": [];
  "save-target": [];
  "change-mode": [mode: RewriteMode];
  "generate-ca": [];
}>();

const metrics = computed<MetricItem[]>(() => [
  {
    label: "请求",
    value: props.stats.request_total ?? 0,
    tone: "info",
    icon: StatsChartOutline,
  },
  {
    label: "成功",
    value: props.stats.patch_success ?? 0,
    tone: "success",
    icon: ShieldCheckmarkOutline,
  },
  {
    label: "Noop",
    value: props.stats.patch_noop ?? 0,
    tone: "neutral",
    icon: RadioButtonOnOutline,
  },
  {
    label: "透传",
    value: props.stats.pass_through_total ?? 0,
    tone: "neutral",
    icon: RefreshOutline,
  },
  {
    label: "错误",
    value: props.stats.patch_error ?? 0,
    tone: "danger",
    icon: OptionsOutline,
  },
  {
    label: "拒绝",
    value: props.stats.reject_total ?? 0,
    tone: "warning",
    icon: PowerOutline,
  },
]);

function emitFormRef(el: Element | null) {
  emit("form-ref", el as FormInst | null);
}
</script>

<template>
  <n-spin :show="loading">
    <n-space v-if="status" vertical size="medium">
      <n-card size="small" class="summary-card">
        <div class="summary-layout">
          <div class="summary-metrics">
            <div
              v-for="item in metrics"
              :key="item.label"
              class="metric-item"
              :class="`metric-${item.tone}`"
            >
              <div class="metric-label">
                <n-icon class="metric-icon">
                  <component :is="item.icon" />
                </n-icon>
                <span>{{ item.label }}</span>
              </div>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </n-card>

      <section class="main-grid">
        <n-card
          size="small"
          class="panel-card target-card"
          :segmented="{ content: true }"
        >
          <template #header>
            <div class="card-title">
              <n-icon :component="LocationOutline" />
              <span>模拟上游位置</span>
            </div>
          </template>
          <template #header-extra>
            <n-button
              size="small"
              quaternary
              class="reset-button"
              :loading="saving"
              @click="emit('reset-state')"
            >
              <template #icon>
                <n-icon :component="RefreshOutline" />
              </template>
              恢复默认运行时状态
            </n-button>
          </template>
          <p class="card-description">
            设置本次完整性测试使用的模拟上游经纬度。保存后会写入代理运行时配置。
          </p>
          <n-form
            :ref="emitFormRef"
            :model="form"
            :rules="rules"
            label-placement="top"
            class="target-form"
          >
            <div class="favorite-location-row">
              <n-select
                :value="selectedFavoriteKey"
                :options="favoriteOptions"
                placeholder="选择收藏地址"
                clearable
                :disabled="!favoriteOptions.length"
                @update:value="emit('apply-favorite', $event)"
              />
            </div>
            <n-form-item
              label="名称（可选）"
              path="name"
              :show-feedback="false"
            >
              <n-input
                v-model:value="form.name"
                placeholder="中国上海市黄浦区人民广场"
              />
            </n-form-item>
            <div class="form-grid">
              <n-form-item label="纬度" path="lat" :show-feedback="false">
                <n-input-number
                  v-model:value="form.lat"
                  :min="-90"
                  :max="90"
                  :precision="8"
                  clearable
                />
              </n-form-item>
              <n-form-item label="经度" path="lng" :show-feedback="false">
                <n-input-number
                  v-model:value="form.lng"
                  :min="-180"
                  :max="180"
                  :precision="8"
                  clearable
                />
              </n-form-item>
            </div>
            <n-form-item label="scale" path="scale" :show-feedback="false">
              <n-input-number
                v-model:value="form.scale"
                :min="0"
                :max="10"
                :step="0.1"
                clearable
              />
            </n-form-item>
            <n-space justify="end" class="form-actions">
              <n-button
                secondary
                :disabled="!canFavoriteCurrentTarget"
                @click="emit('favorite-current')"
              >
                收藏地址
              </n-button>
              <n-button
                secondary
                :disabled="loading || !status"
                @click="emit('open-map-picker')"
              >
                <template #icon>
                  <n-icon :component="LocationOutline" />
                </template>
                地图选点
              </n-button>
              <n-button
                type="primary"
                :loading="saving"
                @click="emit('save-target')"
              >
                保存实验位置
              </n-button>
            </n-space>
          </n-form>
        </n-card>

        <aside class="side-stack">
          <n-card
            size="small"
            class="panel-card"
            :segmented="{ content: true }"
          >
            <template #header>
              <div class="card-title">
                <n-icon :component="OptionsOutline" />
                <span>信号变换模式</span>
              </div>
            </template>
            <n-radio-group
              :value="target.mode"
              class="mode-group"
              @update:value="emit('change-mode', $event)"
            >
              <div class="mode-options">
                <n-radio
                  v-for="option in modeOptions"
                  :key="option.value"
                  :value="option.value"
                  class="mode-option"
                  :class="{ 'is-active': target.mode === option.value }"
                >
                  <div class="mode-label">
                    <strong>{{ option.label }}</strong>
                    <span>{{ option.description }}</span>
                  </div>
                </n-radio>
              </div>
            </n-radio-group>
          </n-card>

          <n-card
            size="small"
            class="panel-card"
            :segmented="{ content: true }"
          >
            <template #header>
              <div class="card-title">
                <n-icon :component="ShieldCheckmarkOutline" />
                <span>只读代理策略</span>
              </div>
            </template>
            <n-list
              v-if="allowRules.length"
              size="small"
              class="sample-list"
              :show-divider="false"
            >
              <n-list-item
                v-for="(rule, index) in allowRules"
                :key="`${rule.host}-${index}`"
                class="sample-item"
              >
                <div>
                  <div>
                    <span class="code-pill">{{ rule.host }}</span>
                  </div>
                  <div class="muted-text">
                    paths: {{ rule.paths?.join(", ") || "-" }} · pass other:
                    {{ rule.pass_through_other_paths ? "yes" : "no" }}
                  </div>
                </div>
              </n-list-item>
            </n-list>
            <n-empty v-else description="暂无 allow rule" size="small" />
          </n-card>
        </aside>
      </section>

      <section class="detail-grid">
        <n-card size="small" class="panel-card" :segmented="{ content: true }">
          <template #header>
            <div class="card-title">
              <n-icon :component="DocumentTextOutline" />
              <span>最近一次测试结果</span>
            </div>
          </template>
          <n-empty v-if="!lastPatch" description="暂无测试记录" size="small" />
          <template v-else>
            <n-descriptions label-placement="left" :column="1" size="small">
              <n-descriptions-item
                v-for="row in lastPatchRows"
                :key="row.label"
                :label="row.label"
              >
                <span class="code-pill">{{ row.value }}</span>
              </n-descriptions-item>
            </n-descriptions>
            <n-list
              v-if="lastPatch.sample?.length"
              size="small"
              class="sample-list"
              :show-divider="false"
            >
              <n-list-item
                v-for="(item, index) in lastPatch.sample"
                :key="`${item}-${index}`"
                class="sample-item"
              >
                {{ item }}
              </n-list-item>
            </n-list>
          </template>
        </n-card>

        <n-card
          size="small"
          class="panel-card ca-card"
          :segmented="{ content: true }"
        >
          <template #header>
            <div class="card-title">
              <n-icon :component="DownloadOutline" />
              <span>CA 证书</span>
            </div>
          </template>
          <n-space vertical>
            <n-text depth="3" class="muted-text">
              下载当前 mitmproxy CA，并在 iPhone 上完整信任。
            </n-text>
            <n-alert v-if="!ca.available" type="warning" size="small">
              后端尚未生成 CA 文件，请先启动 mitmproxy 代理。
            </n-alert>
            <n-space>
              <n-button
                secondary
                type="primary"
                :loading="caBusy"
                @click="emit('generate-ca')"
              >
                <template #icon>
                  <n-icon :component="RefreshOutline" />
                </template>
                {{ ca.available ? "重新生成证书" : "生成证书" }}
              </n-button>
              <n-button
                tag="a"
                :href="caUrl"
                secondary
                type="primary"
                :disabled="!ca.available"
              >
                <template #icon>
                  <n-icon :component="DownloadOutline" />
                </template>
                下载 ca.cer
              </n-button>
            </n-space>
          </n-space>
        </n-card>
      </section>
    </n-space>
  </n-spin>
</template>
