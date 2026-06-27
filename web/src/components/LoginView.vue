<script setup lang="ts">
import { reactive, ref } from "vue";
import type { FormInst, FormRules } from "naive-ui";
import { NIcon } from "naive-ui";
import {
  KeyOutline,
  LogInOutline,
  ShieldCheckmarkOutline,
} from "@vicons/ionicons5";
import type { LoginPayload } from "../types";

defineProps<{
  loading?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  login: [payload: LoginPayload];
}>();

const formRef = ref<FormInst | null>(null);
const form = reactive<LoginPayload>({
  username: "",
  password: "",
});

const rules: FormRules = {
  username: {
    required: true,
    message: "请输入用户名",
    trigger: ["input", "blur"],
  },
  password: {
    required: true,
    message: "请输入密码",
    trigger: ["input", "blur"],
  },
};

async function submit() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  emit("login", { ...form });
}
</script>

<template>
  <div class="login-shell">
    <n-card class="login-card">
      <div class="login-heading">
        <div class="login-mark">
          <n-icon :component="ShieldCheckmarkOutline" />
        </div>
        <div>
          <h1>登录 GSLOC-PROXY</h1>
        </div>
      </div>

      <n-alert v-if="error" type="error" class="login-alert">
        {{ error }}
      </n-alert>

      <n-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @submit.prevent="submit"
      >
        <n-form-item label="用户名" path="username">
          <n-input
            v-model:value="form.username"
            autocomplete="username"
            :disabled="loading"
          />
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input
            v-model:value="form.password"
            type="password"
            show-password-on="click"
            autocomplete="current-password"
            :disabled="loading"
            @keyup.enter="submit"
          >
            <template #prefix>
              <n-icon :component="KeyOutline" />
            </template>
          </n-input>
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="submit">
          <template #icon>
            <n-icon :component="LogInOutline" />
          </template>
          登录
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
