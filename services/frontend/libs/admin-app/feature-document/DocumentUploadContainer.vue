<script lang="ts" setup>
import { OnyxIcon } from '@shared/ui';
import { allowedDocumentAccepts, allowedDocumentDisplayNames, isAllowedDocumentType } from '@shared/utils';
import { authService } from '@shared/auth/auth.service';
import { iconCircleInformation, iconCloudArrowUp, iconGlobe, iconX } from '@sit-onyx/icons';
import { computed, onMounted, ref } from "vue";
import { useI18n } from 'vue-i18n';
import { useDocumentsStore } from '../data-access/+state/documents.store';
import { UploadedDocument } from '../models/uploaded-document.model';
import UploadedDocumentItem from '../ui/UploadedDocumentItem.vue';

const store = useDocumentsStore();
const {t} = useI18n();
const isDragOver = ref(false);
const fileInputRef = ref<HTMLInputElement>();
const uploadedDocuments = computed((): UploadedDocument[] => store.uploadedDocuments);
const isInvalidFileType = ref(false);
const uploadMethod = ref<'file' | 'confluence' | 'sitemap'>('file');
const allowedFileTypesLabel = allowedDocumentDisplayNames.join(', ');
const allowedFileInputAccept = allowedDocumentAccepts.join(',');
const uploadTargetOptions = ref<{ id: string; label: string }[]>([
  { id: 'my_tenant', label: t('documents.targetMyTenant') },
]);
const selectedTargetSpaceId = ref('my_tenant');

const runtimeConfig = (window as any).config || {};
const isPlaceholder = (value: string | undefined) => !value || /^VITE_[A-Z0-9_]+$/.test(value);
const pickValue = (...candidates: Array<string | undefined>) => candidates.find((v) => !isPlaceholder(v));
const uploadSharingFlag = String(
  pickValue(runtimeConfig.VITE_ENABLE_UPLOAD_SHARING_TARGET, import.meta.env.VITE_ENABLE_UPLOAD_SHARING_TARGET, 'false')
).toLowerCase() === 'true';

const showUploadTargetSelector = computed(
  () => uploadSharingFlag && uploadTargetOptions.value.length > 1
);

const toBool = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string') return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
  return false;
};

const toStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    return value.includes(',')
      ? value.split(',').map((item) => item.trim()).filter(Boolean)
      : [value.trim()];
  }
  return [];
};

const decodeJwtClaims = (token: string): Record<string, unknown> | null => {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const normalized = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
};

const resolveTargetSpaceId = (): string | undefined => {
  if (!showUploadTargetSelector.value) return undefined;
  if (selectedTargetSpaceId.value === 'my_tenant') return undefined;
  return selectedTargetSpaceId.value;
};

onMounted(async () => {
  if (!uploadSharingFlag) return;
  const token = await authService.getAccessToken();
  if (!token) return;
  const claims = decodeJwtClaims(token);
  if (!claims) return;

  const options: Array<{ id: string; label: string }> = [{ id: 'my_tenant', label: t('documents.targetMyTenant') }];
  const domainIds = toStringList(claims.allowed_domain_ids);
  if (toBool(claims.can_write_shared_domain)) {
    for (const domainId of domainIds) {
      options.push({
        id: `shared_${domainId}`,
        label: t('documents.targetSharedDomain', { domain: domainId }),
      });
    }
  }
  if (toBool(claims.can_write_global)) {
    options.push({ id: 'shared_global', label: t('documents.targetGlobal') });
  }
  uploadTargetOptions.value = options;
});


// confluence configuration refs
const confluenceName = ref('');
const spaceKey = ref('');
const confluenceToken = ref('');
const confluenceUrl = ref('');
const maxPages = ref<number>();
const confluenceCql = ref('');

  // sitemap configuration refs
  const sitemapName = ref('');
  const sitemapWebPath = ref('');
  const sitemapFilterUrls = ref('');
  const sitemapHeaderTemplate = ref('');
  const sitemapParser = ref<'docusaurus' | 'astro' | 'generic' | undefined>(undefined);
  const sitemapContinueOnFailure = ref(true);

  const error = computed(() => store.error);

  type SitemapParser = 'docusaurus' | 'astro' | 'generic';
  const isSitemapParser = (value: unknown): value is SitemapParser =>
      value === 'docusaurus' || value === 'astro' || value === 'generic';

  const uploadDocuments = (files: File[]) => {
      if (files.some(file => !isAllowedDocumentType(file.name, file.type))) {
          isInvalidFileType.value = true;
          return;
      }

    isInvalidFileType.value = false;
    store.uploadDocuments(files, resolveTargetSpaceId());
}

const onFileInputChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    const files = Array.from(target.files!);
    uploadDocuments(files);
    target.value = '';
}

const onDrop = (event: DragEvent) => {
    event.preventDefault();
    isDragOver.value = false;
    const files = Array.from(event.dataTransfer!.files);
    uploadDocuments(files);
}

const onDragOver = (event: DragEvent) => {
    event.preventDefault();
    isDragOver.value = true;
}

const onDragLeave = () => {
    isDragOver.value = false;
}

const onRemoveDocument = (documentId: string) => {
    store.removeUploadedDocument(documentId);
}

const handleConfluenceUpload = () => {
    // send configured parameters to backend
    store.loadConfluence({
        name: confluenceName.value,
        spaceKey: spaceKey.value,
        token: confluenceToken.value,
        url: confluenceUrl.value,
        maxPages: maxPages.value,
        cql: confluenceCql.value,
    }, resolveTargetSpaceId());
}

  const handleSitemapUpload = () => {
      const parser = sitemapParser.value;
      if (parser !== undefined && !isSitemapParser(parser)) {
          store.error = 'sitemap';
          return;
      }
      // send configured parameters to backend
      store.loadSitemap({
          name: sitemapName.value,
          webPath: sitemapWebPath.value,
          filterUrls: sitemapFilterUrls.value,
          headerTemplate: sitemapHeaderTemplate.value,
          parser,
          continueOnFailure: sitemapContinueOnFailure.value,
      }, resolveTargetSpaceId());
  }

const clearError = () => {
    store.error = null
}

const getErrorMessage = (errorType: string) => {
    switch (errorType) {
        case 'delete':
            return t('documents.deleteError');
        case 'upload':
            return t('documents.uploadError');
        case 'load':
            return t('documents.loadError');
        case 'confluence':
            return t('documents.confluenceError');
        case 'confluence_not_configured':
            return t('documents.confluenceNotConfigured');
        case 'confluence_locked':
            return t('documents.confluenceLocked');
        case 'sitemap':
            return t('documents.sitemapError');
        case 'sitemap_not_configured':
            return t('documents.sitemapNotConfigured');
        case 'sitemap_locked':
            return t('documents.sitemapLocked');
        default:
            return t('documents.unknownError');
    }
}
</script>

<template>
    <div class="flex justify-center items-center min-w-full min-h-full">
        <div class="flex flex-col w-full max-w-3xl">
            <!-- Error message -->
            <div v-if="error" role="alert"
                class="alert alert-error mb-4 slide-in-down flex justify-between items-center">
                <div class="flex items-center">
                    <OnyxIcon :icon="iconCircleInformation" :size="24" class="mr-2" />
                    <div>
                        <h3 class="font-bold">{{ t('documents.errorOccurred') }}</h3>
                        <div class="text-sm">{{ getErrorMessage(error) }}</div>
                    </div>
                </div>
                <button @click="clearError" class="btn btn-ghost btn-sm">
                    <OnyxIcon :icon="iconX" :size="20" />
                </button>
            </div>

            <!-- Upload method tabs -->
            <div class="tabs tabs-boxed mb-4">
                <a class="tab" :class="{'tab-active': uploadMethod === 'file'}" @click="uploadMethod = 'file'">
                    {{ t('documents.fileUpload') }}
                </a>
                <a class="tab" :class="{'tab-active': uploadMethod === 'confluence'}"
                    @click="uploadMethod = 'confluence'">
                    {{ t('documents.confluenceUpload') }}
                </a>
                <a class="tab" :class="{'tab-active': uploadMethod === 'sitemap'}"
                    @click="uploadMethod = 'sitemap'">
                    {{ t('documents.sitemapUpload') }}
                </a>
            </div>

            <div v-if="showUploadTargetSelector" class="mb-4 p-3 rounded-box border border-base-300 bg-base-100">
                <label for="upload-target" class="font-medium text-sm">{{ t('documents.uploadTargetLabel') }}</label>
                <select id="upload-target" v-model="selectedTargetSpaceId" class="select select-bordered w-full mt-2">
                    <option v-for="option in uploadTargetOptions" :key="option.id" :value="option.id">
                        {{ option.label }}
                    </option>
                </select>
                <p class="text-xs opacity-60 mt-1">{{ t('documents.uploadTargetInfo') }}</p>
            </div>

            <!-- File upload area -->
            <div v-if="uploadMethod === 'file'"
                class="flex flex-col m-auto justify-center items-center w-full h-96 bg-base-100 rounded-box border border-base-300 border-dashed"
                :class="{'bg-base-200': isDragOver}" @dragover.prevent="onDragOver" @dragleave.prevent="onDragLeave"
                @drop.prevent="onDrop">
                <div class="flex flex-col justify-center items-center pt-5 pb-6">
                    <OnyxIcon :icon="iconCloudArrowUp" :size="40" class="mb-4 text-primary" />
                    <p class="mb-1 font-bold text-cente">{{ t('documents.uploadSelectTitle') }}</p>
                    <p class="text-xs opacity-50">{{ t('documents.uploadSelectDescription') }} {{ allowedFileTypesLabel }}</p>

                    <button class="btn btn-sm mt-4 btn-accent" @click="fileInputRef!.click()">{{ t('documents.select')
                        }}</button>
                </div>
                <input ref="fileInputRef" type="file" multiple :accept="allowedFileInputAccept" @change="onFileInputChange"
                    class="hidden" />
            </div>

            <!-- Confluence load area -->
            <div v-else-if="uploadMethod === 'confluence'"
                class="flex flex-col m-auto justify-center items-center w-full h-112 bg-base-100 rounded-box border border-base-300">
                <div class="flex flex-col justify-center items-center pt-5 pb-6">
                    <OnyxIcon :icon="iconGlobe" :size="40" class="mb-4 text-primary" />
                    <p class="mb-1 font-bold">{{ t('documents.confluenceLoadTitle') }}</p>
                    <!-- configuration inputs -->
                    <div class="space-y-2 mb-4 w-full max-w-sm">
                      <label for="confluenceUrl" class="sr-only">Confluence URL</label>
                      <input v-model="confluenceUrl" type="url" placeholder="URL" class="input input-bordered w-full" />
                      <label for="confluenceName" class="sr-only"> Confluence Name</label>
                      <input v-model="confluenceName" type="text" placeholder="Name" class="input input-bordered w-full" />
                      <label for="spaceKey" class="sr-only">Space key</label>
                      <input v-model="spaceKey" type="text" placeholder="Space key (optional)" class="input input-bordered w-full" />
                      <label for="confluenceCql" class="sr-only">CQL</label>
                      <input v-model="confluenceCql" type="text" placeholder="CQL query (optional)" class="input input-bordered w-full" />
                      <label for="confluenceToken" class="sr-only">Token</label>
                      <input v-model="confluenceToken" type="password" placeholder="Token" class="input input-bordered w-full" />
                      <label for="maxPages" class="sr-only">Max pages</label>
                      <input v-model.number="maxPages" type="number" placeholder="Max number of pages (optional)" class="input input-bordered w-full" />
                    </div>
                    <p class="text-xs opacity-50">{{ t('documents.confluenceLoadDescription') }}</p>
                    <p class="text-xs opacity-50 mb-4">{{ t('documents.confluenceQueryHint') }}</p>
                    <button class="btn btn-sm btn-accent" @click="handleConfluenceUpload">
                        {{ t('documents.loadConfluence') }}
                    </button>
                </div>
            </div>

            <!-- Sitemap load area -->
            <div v-else-if="uploadMethod === 'sitemap'"
                class="flex flex-col m-auto justify-center items-center w-full h-112 bg-base-100 rounded-box border border-base-300">
                <div class="flex flex-col justify-center items-center pt-5 pb-6">
                    <OnyxIcon :icon="iconGlobe" :size="40" class="mb-4 text-primary" />
                    <p class="mb-1 font-bold">{{ t('documents.sitemapLoadTitle') }}</p>
                    <!-- configuration inputs -->
                    <div class="space-y-2 mb-4 w-full max-w-sm">
                      <label for="sitemapName" class="sr-only">Sitemap Name</label>
                      <input id="sitemapName" v-model="sitemapName" type="text" placeholder="Name" class="input input-bordered w-full" required/>
                      <label for="sitemapWebPath" class="sr-only">Sitemap URL</label>
                      <input v-model="sitemapWebPath" type="url" placeholder="Sitemap URL (required)" class="input input-bordered w-full" required />
                      <label for="sitemapParser" class="sr-only">Parser</label>
                      <select id="sitemapParser" v-model="sitemapParser" class="select select-bordered w-full">
                                                <option :value="undefined">{{ t('documents.sitemapParserAuto') }}</option>
                        <option value="astro">{{ t('documents.sitemapParserAstro') }}</option>
                        <option value="docusaurus">{{ t('documents.sitemapParserDocusaurus') }}</option>
                        <option value="generic">{{ t('documents.sitemapParserGeneric') }}</option>
                      </select>
                      <label for="sitemapFilterUrls" class="sr-only">Filter URLs</label>
                      <textarea v-model="sitemapFilterUrls" placeholder="Filter URLs (optional) - one regex pattern per line" class="textarea textarea-bordered w-full" rows="3"></textarea>
                      <label for="sitemapHeaderTemplate" class="sr-only">Headers JSON</label>
                      <textarea v-model="sitemapHeaderTemplate" placeholder="Headers (optional) - JSON format: {&quot;Authorization&quot;: &quot;Bearer token&quot;}" class="textarea textarea-bordered w-full" rows="2"></textarea>
                      <label class="flex items-center justify-between text-sm">
                        <span>{{ t('documents.sitemapContinueOnFailure') }}</span>
                        <input
                          v-model="sitemapContinueOnFailure"
                          type="checkbox"
                          class="checkbox checkbox-sm"
                          :title="t('documents.sitemapContinueOnFailureHint')"
                        />
                      </label>
                    </div>
                    <p class="text-xs opacity-50 mb-4">{{ t('documents.sitemapLoadDescription') }}</p>
                    <button class="btn btn-sm btn-accent" @click="handleSitemapUpload">
                        {{ t('documents.loadSitemap') }}
                    </button>
                </div>
            </div>

            <!-- Uploaded documents -->
            <div class="mx-auto mt-4 w-full">
                <div class="mb-4" v-for="uploadDocument in uploadedDocuments" :key="uploadDocument.id">
                    <UploadedDocumentItem class="slide-in-down" :removeItem="onRemoveDocument" :data="uploadDocument" />
                </div>
            </div>

            <!-- Invalid file type message -->
            <div role="alert" v-if="isInvalidFileType" @click="isInvalidFileType = false"
                class="alert alert-warning cursor-pointer mb-2 slide-in-down">
                <OnyxIcon :icon="iconCircleInformation" :size="24" class="mr-2" />
                <div>
                    <h3 class="font-bold">{{ t('documents.fileTypeNotAllowedTitle') }}</h3>
                    <div class="text-xs">{{ t('documents.fileTypeNotAllowedDescription') }} {{ allowedFileTypesLabel }}</div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.slide-in-down {
    animation: slide-in-down 0.3s ease-out;
}

@keyframes slide-in-down {
    0% {
        transform: translateY(-15%);
    }

    100% {
        transform: translateY(0);
    }
}
</style>
