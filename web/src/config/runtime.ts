import type { FormRules } from "naive-ui";

export const modeOptions = [
  {
    label: "clamp",
    value: "clamp",
    description: "压缩点云到目标点附近，默认推荐。",
  },
  {
    label: "shift",
    value: "shift",
    description: "保留原始点云形状并整体平移。",
  },
] as const;

export const targetRules: FormRules = {
  lat: {
    required: true,
    type: "number",
    min: -90,
    max: 90,
    message: "纬度需要是 -90 到 90 之间的数字",
    trigger: ["blur", "input"],
  },
  lng: {
    required: true,
    type: "number",
    min: -180,
    max: 180,
    message: "经度需要是 -180 到 180 之间的数字",
    trigger: ["blur", "input"],
  },
  scale: {
    required: true,
    type: "number",
    min: 0,
    max: 10,
    message: "scale 需要是 0 到 10 之间的数字",
    trigger: ["blur", "input"],
  },
};
