<script setup lang="ts">
import type { ComponentPublicInstance } from "vue";
import { NIcon } from "naive-ui";
import { SearchOutline } from "@vicons/ionicons5";
import { formatNumber } from "../utils/format";
import {
  formatSearchResultMeta,
  formatSearchResultName,
} from "../utils/geocode";
import type { GeocodeResult, PickedLatLng, PlaceSearchState } from "../types";

withDefaults(
  defineProps<{
    show?: boolean;
    placeSearch: PlaceSearchState;
    pickedLatLng: PickedLatLng;
  }>(),
  {
    show: false,
  },
);

const emit = defineEmits<{
  "update:show": [value: boolean];
  "map-ref": [value: HTMLElement | null];
  "after-leave": [];
  "close-results": [];
  search: [];
  "apply-search-result": [result: GeocodeResult];
  close: [];
  "apply-picked": [];
}>();

function emitMapRef(el: Element | ComponentPublicInstance | null) {
  emit("map-ref", el instanceof HTMLElement ? el : null);
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="地图选点"
    class="map-picker-modal"
    :bordered="false"
    :auto-focus="false"
    @update:show="emit('update:show', $event)"
    @after-leave="emit('after-leave')"
  >
    <div class="map-picker-body" @click="emit('close-results')">
      <div class="map-search-panel" @click.stop>
        <div class="map-search">
          <n-input
            v-model:value="placeSearch.query"
            placeholder="搜索地名，例如：人民广场、东京塔、Apple Park"
            clearable
            @keyup.enter="emit('search')"
          >
            <template #prefix>
              <n-icon :component="SearchOutline" />
            </template>
          </n-input>
          <n-button
            type="primary"
            :loading="placeSearch.loading || pickedLatLng.loading"
            @click="emit('search')"
          >
            <template #icon>
              <n-icon :component="SearchOutline" />
            </template>
            搜索
          </n-button>
        </div>
        <div
          v-if="placeSearch.results.length || placeSearch.error"
          class="map-search-results"
        >
          <n-alert v-if="placeSearch.error" type="warning" size="small">
            {{ placeSearch.error }}
          </n-alert>
          <button
            v-for="result in placeSearch.results"
            :key="result.place_id"
            type="button"
            class="map-search-result"
            @click="emit('apply-search-result', result)"
          >
            <span class="map-search-result-name">
              {{ formatSearchResultName(result) }}
            </span>
            <span class="map-search-result-meta">
              {{ formatSearchResultMeta(result) }}
            </span>
          </button>
        </div>
      </div>
      <div :ref="emitMapRef" class="map-picker-map"></div>
      <div class="map-picker-coordinates">
        <span>纬度：{{ formatNumber(pickedLatLng.lat, 8) }}</span>
        <span>经度：{{ formatNumber(pickedLatLng.lng, 8) }}</span>
      </div>
      <n-space justify="end">
        <n-button @click="emit('close')">取消</n-button>
        <n-button type="primary" @click="emit('apply-picked')">
          应用到目标
        </n-button>
      </n-space>
    </div>
  </n-modal>
</template>
