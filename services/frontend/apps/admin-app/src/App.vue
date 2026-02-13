<script lang="ts" setup>
import { RouterView } from "vue-router";
import { NavigationContainer, OnyxIcon } from "@shared/ui";
import { useI18n } from "vue-i18n";
import { iconArrowSmallUpRightTop } from "@sit-onyx/icons";

const runtimeConfig = (window as any).config || {};
const isPlaceholder = (value: string | undefined) =>
  !value || /^VITE_[A-Z0-9_]+$/.test(value);
const pickValue = (...candidates: Array<string | undefined>) =>
  candidates.find((v) => !isPlaceholder(v));

const { t } = useI18n();
const chatURL = pickValue(
  runtimeConfig.VITE_CHAT_URL,
  import.meta.env.VITE_CHAT_URL
);
</script>

<template>
  <main class="bg-base-100 flex flex-col overflow-hidden">
    <NavigationContainer>
      <a
        class="flex gap-2 items-center btn btn-primary btn-sm"
        target="_blank"
        :href="chatURL"
      >
        <OnyxIcon :icon="iconArrowSmallUpRightTop" :size="16" />
        {{ t("documents.chat") }}
      </a>
    </NavigationContainer>
    <RouterView class="flex-1" />
  </main>
</template>

<style lang="css">
@import "@shared/style";
</style>
