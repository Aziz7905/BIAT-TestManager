// src/api/client.ts
import axios from "axios";
import type {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";
const ACCESS_TOKEN_KEY = "access";
const REFRESH_TOKEN_KEY = "refresh";

interface RetryableRequestConfig extends AxiosRequestConfig {
  _retry?: boolean;
}

const getAccessToken = (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY);

const getRefreshToken = (): string | null =>
  localStorage.getItem(REFRESH_TOKEN_KEY);

const setAccessToken = (token: string): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
};

const clearStoredTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

const shouldSkipRefresh = (url?: string): boolean => {
  if (!url) {
    return false;
  }

  return ["/login/", "/logout/", "/refresh/"].some((path) => url.includes(path));
};

const attachAuthorizationHeader = <T extends { headers?: unknown }>(
  config: T,
  token: string
): T => {
  const headers =
    config.headers && typeof config.headers === "object"
      ? (config.headers as Record<string, string>)
      : {};

  return {
    ...config,
    headers: {
      ...headers,
      Authorization: `Bearer ${token}`,
    },
  };
};

const authClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

let refreshPromise: Promise<string> | null = null;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();

  if (token) {
    return attachAuthorizationHeader(config, token);
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;
    const statusCode = error.response?.status;

    if (
      !originalRequest ||
      statusCode !== 401 ||
      originalRequest._retry ||
      shouldSkipRefresh(originalRequest.url)
    ) {
      return Promise.reject(error);
    }

    const refreshToken = getRefreshToken();

    if (!refreshToken) {
      clearStoredTokens();
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = authClient
          .post<{ access: string }>("/refresh/", { refresh: refreshToken })
          .then((response) => {
            setAccessToken(response.data.access);
            return response.data.access;
          })
          .catch((refreshError) => {
            clearStoredTokens();
            throw refreshError;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }

      const newAccessToken = await refreshPromise;
      const requestWithNewToken = attachAuthorizationHeader(
        originalRequest,
        newAccessToken
      );

      return apiClient(requestWithNewToken);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  }
);
