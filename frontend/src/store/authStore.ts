// src/store/authStore.ts
import { create } from "zustand";
import { getCurrentUser, login as loginRequest, logout as logoutRequest } from "../api/auth";
import type { CurrentUser } from "../types/accounts";

interface AuthState {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  initializeAuth: () => Promise<void>;
  clearAuth: () => void;
}

const ACCESS_TOKEN_KEY = "access";
const REFRESH_TOKEN_KEY = "refresh";

const clearStoredTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

const hasStoredSession = (): boolean =>
  Boolean(
    localStorage.getItem(ACCESS_TOKEN_KEY) ||
      localStorage.getItem(REFRESH_TOKEN_KEY)
  );

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: hasStoredSession(),
  isLoading: false,

  async login(identifier: string, password: string) {
    set({ isLoading: true });

    try {
      const data = await loginRequest({ identifier, password });

      set({
        user: data.user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      clearStoredTokens();
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      throw error;
    }
  },

  async logout() {
    try {
      await logoutRequest();
    } catch {
      // Ignore logout API failures and clear local session anyway.
    }

    clearStoredTokens();

    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  async initializeAuth() {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

    if (!accessToken && !refreshToken) {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      return;
    }

    set({ isLoading: true });

    try {
      const user = await getCurrentUser();

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      clearStoredTokens();

      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  clearAuth() {
    clearStoredTokens();

    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },
}));
