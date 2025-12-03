import axios from 'axios';
import { authService } from '@shared/auth/auth.service';
import { ChatRequestModel } from "../models/chat-request.model";
import { ChatResponseModel } from "../models/chat-response.model";

const runtimeConfig = (window as any).config || {};
const isPlaceholder = (value: string | undefined) =>
  !value || /^VITE_[A-Z0-9_]+$/.test(value);

const pickValue = (...candidates: Array<string | undefined>) =>
  candidates.find((v) => !isPlaceholder(v));

const rawBaseUrl = pickValue(
  runtimeConfig.VITE_API_URL,
  import.meta.env.VITE_API_URL,
  window.location.origin
);
const normalizedBaseUrl = rawBaseUrl?.replace(/\/+$/, '') || '';
const apiBaseUrl = /\/api$/.test(normalizedBaseUrl)
  ? normalizedBaseUrl
  : `${normalizedBaseUrl}/api`;

const apiClient = axios.create({
  baseURL: apiBaseUrl
});

// Attach Keycloak access token to every chat API request
apiClient.interceptors.request.use(async (config) => {
  const token = await authService.getAccessToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export class ChatAPI {
    static async callInference(request: ChatRequestModel): Promise<ChatResponseModel> {
        const response = await apiClient.post<ChatResponseModel>(`/chat/${request.session_id}`, request);
        return response.data;
    }
}
