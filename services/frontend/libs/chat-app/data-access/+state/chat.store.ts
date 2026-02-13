import { settings } from "@shared/settings";
import { newUid } from "@shared/utils";
import { authService } from "@shared/auth/auth.service";
import { marked } from "marked";
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { i18n } from "@i18n/chat";
import {
  ChatDocumentModel,
  mapToChatDocuments,
} from "../../models/chat-document.model";
import { ChatMessageModel } from "../../models/chat-message.model";
import { ChatRequestModel, mapToChatRequestModel } from "../../models/chat-request.model";
import { InformationPiece } from "../../models/chat-response.model";
import { DocumentResponseModel } from "../../models/document-response.model";
import { ChatAPI } from "../chat.api";

interface ScopeOption {
  id: string;
  label: string;
}

export const useChatStore = defineStore("chat", () => {
  const SCOPE_STORAGE_KEY = "chat.scope.selection.v1";
  const runtimeConfig = (window as any).config || {};
  const isPlaceholder = (value: string | undefined) => !value || /^VITE_[A-Z0-9_]+$/.test(value);
  const pickValue = (...candidates: Array<string | undefined>) => candidates.find((value) => !isPlaceholder(value));
  const conversationId = ref();
  const chatHistory = ref<ChatMessageModel[]>([]);
  const chatDocuments = ref<ChatDocumentModel[]>([]);
  const isLoading = ref(false);
  const hasError = ref(false);
  const isSourcesPanelOpen = ref(true);
  const isAuthEnabled = ref(authService.isEnabled());
  const isAuthenticated = ref(false);
  const availableScopes = ref<ScopeOption[]>([{ id: "shared_global", label: "Global" }]);
  const selectedScopeIds = ref<string[]>([]);
  const isScopeSelectorEnabled = computed(
    () =>
      String(
        pickValue(
          runtimeConfig.VITE_ENABLE_SPACE_SELECTOR_IN_CHAT,
          import.meta.env.VITE_ENABLE_SPACE_SELECTOR_IN_CHAT,
          "false",
        ),
      ).toLowerCase() === "true",
  );

  // Use the global i18n instance set up in the app
  const t = i18n.global.t;

  // Placeholder used in i18n templates when interpolation fails upstream
  const BOT_NAME_PLACEHOLDER = "{bot_name}";

  const getInitialMessage = () => {
    try {
      const msg = t("chat.initialMessage", { bot_name: settings.bot.name });
      // Defensive: if interpolation didn't happen for any edge reason, patch it
      if (typeof msg === 'string' && msg.includes(BOT_NAME_PLACEHOLDER)) {
        // Replace all occurrences just in case the placeholder appears multiple times
        return msg.split(BOT_NAME_PLACEHOLDER).join(settings.bot.name);
      }
      return msg as string;
    } catch (error) {
      console.warn("i18n interpolation failed, using fallback", error);
      return `Hi 👋, I'm your AI Assistant ${settings.bot.name}, here to support you with any questions regarding the provided documents!`;
    }
  };
  const lastMessage = () => chatHistory.value[chatHistory.value.length - 1];

  const toStringList = (value: unknown): string[] => {
    if (Array.isArray(value)) {
      return value.map((item) => String(item)).filter(Boolean);
    }
    if (typeof value === "string" && value.trim().length > 0) {
      return value.includes(",")
        ? value.split(",").map((item) => item.trim()).filter(Boolean)
        : [value.trim()];
    }
    return [];
  };

  const persistSelectedScopes = () => {
    localStorage.setItem(SCOPE_STORAGE_KEY, JSON.stringify(selectedScopeIds.value));
  };

  const clearPersistedScopes = () => {
    localStorage.removeItem(SCOPE_STORAGE_KEY);
  };

  const restoreSelectedScopes = () => {
    if (!isScopeSelectorEnabled.value) {
      selectedScopeIds.value = [];
      clearPersistedScopes();
      return;
    }
    try {
      const raw = localStorage.getItem(SCOPE_STORAGE_KEY);
      if (!raw) {
        selectedScopeIds.value = [];
        return;
      }
      const parsed = JSON.parse(raw);
      selectedScopeIds.value = Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
    } catch {
      selectedScopeIds.value = [];
    }
  };

  const normalizeSelectedScopes = () => {
    if (!isScopeSelectorEnabled.value) {
      selectedScopeIds.value = [];
      clearPersistedScopes();
      return;
    }
    const allowed = new Set(availableScopes.value.map((scope) => scope.id));
    selectedScopeIds.value = selectedScopeIds.value.filter((scopeId) => allowed.has(scopeId));
    persistSelectedScopes();
  };

  const updateAvailableScopes = async () => {
    const token = await authService.getAccessToken();
    isAuthenticated.value = Boolean(token);
    if (!token) {
      availableScopes.value = [{ id: "shared_global", label: t("chat.scopeGlobal") as string }];
      normalizeSelectedScopes();
      return;
    }

    const claims = await authService.getAccessTokenClaims();
    const options: ScopeOption[] = [{ id: "shared_global", label: t("chat.scopeGlobal") as string }];
    if (claims) {
      const tenantIds = toStringList((claims as Record<string, unknown>).allowed_tenant_ids);
      const tenantId = (claims as Record<string, unknown>).tenant_id;
      if (tenantId && !tenantIds.includes(String(tenantId))) {
        tenantIds.unshift(String(tenantId));
      }
      for (const id of tenantIds) {
        options.push({ id: `tenant_${id}`, label: `${t("chat.scopeTenant")} ${id}` as string });
      }

      const domainIds = toStringList((claims as Record<string, unknown>).allowed_domain_ids);
      for (const domainId of domainIds) {
        options.push({ id: `shared_${domainId}`, label: `${t("chat.scopeDomain")} ${domainId}` as string });
      }
    }

    availableScopes.value = options;
    normalizeSelectedScopes();
  };

  function addHistory(prompt: { raw: string; html: string }) {
    chatHistory.value.push({
      id: newUid(),
      text: prompt.html,
      rawText: prompt.raw,
      role: "user",
    });

    chatHistory.value.push({
      id: newUid(),
      role: "assistant",
    });
  }

  function updateLatestMessage(update: Partial<ChatMessageModel>) {
    Object.assign(lastMessage(), update);
  }

  function prepareInferenceRequest(prompt: string): ChatRequestModel {
    const cleanedHistory = chatHistory.value.filter(
      (message: ChatMessageModel) => !message.skipAPI,
    );
    const requestMessages = mapToChatRequestModel(
      conversationId.value,
      prompt,
      cleanedHistory,
    );
    return requestMessages;
  }

  function parseDocumentsAsMarkdown(
    documents: InformationPiece[],
  ): Promise<DocumentResponseModel[]> {
    return Promise.all(
      documents.map(async (o) => {
        const chunk = await marked(o.page_content);
        return {
          ...o,
          page_content: chunk,
        } as DocumentResponseModel;
      }),
    );
  }

  const callInference = async (prompt: string) => {
    isLoading.value = true;
    try {
      const requestMessages = prepareInferenceRequest(prompt);

      const promptAsMd = await marked(prompt);
      addHistory({ raw: prompt, html: promptAsMd });

      const response = await ChatAPI.callInference(
        requestMessages,
        isScopeSelectorEnabled.value && selectedScopeIds.value.length > 0 ? selectedScopeIds.value : undefined,
      );

      const textAsMd = await marked(response.answer);
      const documentsAsMd = await parseDocumentsAsMarkdown(response.citations);
      const documents = mapToChatDocuments(
        chatDocuments.value.length,
        documentsAsMd,
        lastMessage().id,
      );

      updateLatestMessage({
        dateTime: new Date(),
        text: textAsMd,
        rawText: response.answer,
        anchorIds: documents.map((o) => o.index),
      });

      chatDocuments.value.push(...documents);
    } catch {
      updateLatestMessage({
        hasError: true,
        dateTime: new Date(),
      });
    } finally {
      isLoading.value = false;
    }
  };

  const initiateConversation = (id: string) => {
    conversationId.value = id;
    restoreSelectedScopes();
    void updateAvailableScopes();
    const initialMessage = getInitialMessage();
    chatHistory.value.push({
      id: newUid(),
      text: initialMessage,
      rawText: initialMessage,
      role: "assistant",
      skipAPI: true,
    });
  };

  const openSourcesPanel = () => {
    isSourcesPanelOpen.value = true;
  };

  const closeSourcesPanel = () => {
    isSourcesPanelOpen.value = false;
  };

  const toggleSourcesPanel = () => {
    isSourcesPanelOpen.value = !isSourcesPanelOpen.value;
  };

  const login = async () => {
    await authService.login();
  };

  const logout = async () => {
    await authService.logout();
    selectedScopeIds.value = [];
    clearPersistedScopes();
    await updateAvailableScopes();
  };

  const toggleScope = (scopeId: string) => {
    if (!isScopeSelectorEnabled.value) {
      return;
    }
    if (selectedScopeIds.value.includes(scopeId)) {
      selectedScopeIds.value = selectedScopeIds.value.filter((id) => id !== scopeId);
    } else {
      selectedScopeIds.value = [...selectedScopeIds.value, scopeId];
    }
    normalizeSelectedScopes();
  };

  const selectAllScopes = () => {
    if (!isScopeSelectorEnabled.value) {
      return;
    }
    selectedScopeIds.value = [];
    persistSelectedScopes();
  };

  return {
    chatDocuments,
    chatHistory,
    isLoading,
    hasError,
    conversationId,
    isSourcesPanelOpen,
    isAuthenticated,
    isAuthEnabled,
    isScopeSelectorEnabled,
    availableScopes,
    selectedScopeIds,
    callInference,
    initiateConversation,
    openSourcesPanel,
    closeSourcesPanel,
    toggleSourcesPanel,
    toggleScope,
    selectAllScopes,
    login,
    logout,
    updateAvailableScopes,
  };
});
