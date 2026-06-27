import { nextTick, reactive, ref } from "vue";
import type { LeafletMouseEvent, Map as LeafletMap, Marker } from "leaflet";
import { createPickerBaseLayers, L } from "../map/leaflet";
import {
  formatReverseGeocodeName,
  formatSearchResultName,
  reverseGeocode,
  searchGeocodePlaces,
} from "../utils/geocode";
import { normalizeLongitude } from "../utils/format";
import type {
  GeocodeResult,
  MessageApi,
  PickedLatLng,
  PlaceSearchState,
  TargetForm,
} from "../types";

interface UseMapPickerOptions {
  form: TargetForm;
  message: MessageApi;
}

interface LatLngPair {
  lat: number;
  lng: number;
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export function useMapPicker({ form, message }: UseMapPickerOptions) {
  const mapPickerVisible = ref(false);
  const mapContainerRef = ref<HTMLElement | null>(null);
  const pickedLatLng = reactive<PickedLatLng>({
    lat: null,
    lng: null,
    name: "",
    loading: false,
  });
  const placeSearch = reactive<PlaceSearchState>({
    query: "",
    loading: false,
    results: [],
    error: "",
  });

  let pickerMap: LeafletMap | null = null;
  let pickerMarker: Marker | null = null;
  let geocodeRequestSeq = 0;
  let placeSearchRequestSeq = 0;
  let placeSearchAbortController: AbortController | null = null;

  function getInitialPickerLatLng(): LatLngPair {
    const lat = Number(form.lat);
    const lng = Number(form.lng);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return { lat, lng };
    }
    return { lat: 31.230416, lng: 121.473701 };
  }

  async function reverseGeocodePickedLocation(lat: number, lng: number) {
    const requestId = ++geocodeRequestSeq;
    pickedLatLng.loading = true;
    pickedLatLng.name = "";

    try {
      const result = await reverseGeocode(lat, lng);
      if (requestId === geocodeRequestSeq) {
        const name = formatReverseGeocodeName(result);
        pickedLatLng.name = name;
        if (name) placeSearch.query = name;
      }
    } catch {
      if (requestId === geocodeRequestSeq) {
        pickedLatLng.name = "";
      }
    } finally {
      if (requestId === geocodeRequestSeq) {
        pickedLatLng.loading = false;
      }
    }
  }

  async function searchPlaces() {
    const query = placeSearch.query.trim();
    placeSearch.error = "";
    placeSearch.results = [];

    if (!query) {
      message.warning("请输入要搜索的地名");
      return;
    }

    const requestId = ++placeSearchRequestSeq;
    placeSearchAbortController?.abort();
    placeSearchAbortController = new AbortController();
    placeSearch.loading = true;

    try {
      const results = await searchGeocodePlaces(query, {
        signal: placeSearchAbortController.signal,
      });
      if (requestId === placeSearchRequestSeq) {
        placeSearch.results = Array.isArray(results) ? results : [];
        if (!placeSearch.results.length) {
          placeSearch.error = "没有找到匹配的地点";
        }
      }
    } catch (err) {
      if (isAbortError(err)) return;
      if (requestId === placeSearchRequestSeq) {
        placeSearch.error = "搜索失败，请稍后重试";
      }
    } finally {
      if (requestId === placeSearchRequestSeq) {
        placeSearch.loading = false;
        placeSearchAbortController = null;
      }
    }
  }

  function applySearchResult(result: GeocodeResult) {
    const lat = Number(result?.lat);
    const lng = Number(result?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      message.warning("这个搜索结果没有有效经纬度");
      return;
    }

    const normalizedLng = Number(normalizeLongitude(lng).toFixed(8));
    const nextLat = Number(lat.toFixed(8));
    const name = formatSearchResultName(result);

    pickedLatLng.lat = nextLat;
    pickedLatLng.lng = normalizedLng;
    pickedLatLng.name = name;
    pickedLatLng.loading = false;
    placeSearch.query = name || result?.display_name || placeSearch.query;
    placeSearch.results = [];
    placeSearch.error = "";

    pickerMarker?.setLatLng([nextLat, normalizedLng]);
    pickerMap?.setView(
      [nextLat, normalizedLng],
      Math.max(pickerMap.getZoom() || 13, 14),
    );
  }

  function closePlaceSearchResults() {
    placeSearch.results = [];
    placeSearch.error = "";
  }

  async function openMapPicker() {
    const initial = getInitialPickerLatLng();
    pickedLatLng.lat = initial.lat;
    pickedLatLng.lng = initial.lng;
    pickedLatLng.name = form.name || "";
    pickedLatLng.loading = false;
    placeSearch.query = form.name || "";
    placeSearch.results = [];
    placeSearch.error = "";
    placeSearch.loading = false;
    cleanupPickerMap();
    mapPickerVisible.value = true;
    await nextTick();
    window.setTimeout(() => initOrRefreshPickerMap(initial), 80);
  }

  function initOrRefreshPickerMap(center: LatLngPair) {
    if (!mapContainerRef.value) return;

    if (!pickerMap) {
      pickerMap = L.map(mapContainerRef.value).setView(
        [center.lat, center.lng],
        13,
      );
      const { defaultLayer, layers } = createPickerBaseLayers();
      defaultLayer.addTo(pickerMap);
      L.control.layers(layers, undefined, { collapsed: false }).addTo(pickerMap);
      pickerMarker = L.marker([center.lat, center.lng]).addTo(pickerMap);
      pickerMap.on("click", (event: LeafletMouseEvent) => {
        const { lat, lng } = event.latlng;
        pickedLatLng.lat = Number(lat.toFixed(8));
        pickedLatLng.lng = Number(normalizeLongitude(lng).toFixed(8));
        pickerMarker?.setLatLng([lat, lng]);
        reverseGeocodePickedLocation(lat, lng);
      });
    } else {
      pickerMap.setView([center.lat, center.lng], pickerMap.getZoom() || 13);
      pickerMarker?.setLatLng([center.lat, center.lng]);
    }

    window.setTimeout(() => pickerMap?.invalidateSize(), 100);
  }

  function applyPickedLocation() {
    if (
      !Number.isFinite(pickedLatLng.lat) ||
      !Number.isFinite(pickedLatLng.lng)
    ) {
      message.warning("请先在地图上选择位置");
      return;
    }
    form.lat = pickedLatLng.lat;
    form.lng = Number(normalizeLongitude(pickedLatLng.lng).toFixed(8));
    form.name = pickedLatLng.name || "";
    closeMapPicker();
  }

  function closeMapPicker() {
    mapPickerVisible.value = false;
    cleanupPickerMap();
  }

  function cleanupPickerMap() {
    placeSearchAbortController?.abort();
    placeSearchAbortController = null;
    placeSearch.loading = false;
    if (pickerMap) {
      pickerMap.remove();
      pickerMap = null;
      pickerMarker = null;
    }
  }

  return {
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
  };
}
