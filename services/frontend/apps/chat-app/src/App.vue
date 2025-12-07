<script lang="ts" setup>
import { onMounted } from "vue";
import { RouterView } from "vue-router";
import { NavigationContainer } from "@shared/ui";
import { useI18n } from "vue-i18n";
import { ArrowTopRightOnSquareIcon } from "@heroicons/vue/24/outline";
import { useThemeStore } from "@shared/store/theme.store";

const runtimeConfig = (window as any).config || {};
const isPlaceholder = (value: string | undefined) =>
  !value || /^VITE_[A-Z0-9_]+$/.test(value);
const pickValue = (...candidates: Array<string | undefined>) =>
  candidates.find((v) => !isPlaceholder(v));

const { t } = useI18n();
const adminURL = pickValue(
  runtimeConfig.VITE_ADMIN_URL,
  import.meta.env.VITE_ADMIN_URL
);

onMounted(() => {
  // Initialize theme
  const themeStore = useThemeStore();
});
</script>

<template>
  <main class="bg-base-100 flex flex-col">
    <NavigationContainer>
      <a
        class="flex gap-2 items-center btn btn-primary border border-opacity-10 border-white btn-sm"
        target="_blank"
        :href="adminURL"
      >
        <ArrowTopRightOnSquareIcon class="w-4 h-4" />
        {{ t("chat.documents") }}
      </a>
    </NavigationContainer>
    <RouterView class="flex-1 overflow-hidden" />
  </main>
</template>

<style lang="css">
@import "@shared/style";
</style>
