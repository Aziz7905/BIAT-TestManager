import { create } from "zustand";
import { tokenStorage } from "../api/client";
import { getMe, login as apiLogin, logout as apiLogout } from "../api/accounts/auth";
import type { User } from "../types/auth";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasHydrated: boolean;
  isHydrating: boolean;
  sessionExpired: boolean;

  bootstrap: () => Promise<void>;
  clearSession: (sessionExpired?: boolean) => void;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

let bootstrapPromise: Promise<void> | null = null;
let hasBootstrapped = false;

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: tokenStorage.getAccess(),
  isAuthenticated: !!tokenStorage.getAccess(),
  isLoading: false,
  hasHydrated: false,
  isHydrating: false,
  sessionExpired: false,

  bootstrap: async () => {
    if (hasBootstrapped) {
      return bootstrapPromise ?? Promise.resolve();
    }

    if (bootstrapPromise) {
      return bootstrapPromise;
    }

    const accessToken = tokenStorage.getAccess();
    if (!accessToken) {
      hasBootstrapped = true;
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        hasHydrated: true,
        isHydrating: false,
        sessionExpired: false,
      });
      return Promise.resolve();
    }

    set({
      accessToken,
      isAuthenticated: true,
      isHydrating: true,
      sessionExpired: false,
    });

    bootstrapPromise = (async () => {
      try {
        const user = await getMe();
        set({
          user,
          accessToken: tokenStorage.getAccess(),
          isAuthenticated: true,
          hasHydrated: true,
          isHydrating: false,
          sessionExpired: false,
        });
      } catch {
        tokenStorage.clear();
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          hasHydrated: true,
          isHydrating: false,
          sessionExpired: true,
        });
      } finally {
        hasBootstrapped = true;
        bootstrapPromise = null;
      }
    })();

    return bootstrapPromise;
  },

  clearSession: (sessionExpired = false) => {
    tokenStorage.clear();
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      hasHydrated: true,
      isHydrating: false,
      sessionExpired,
    });
  },

  login: async (identifier, password) => {
    set({ isLoading: true, sessionExpired: false });
    try {
      const data = await apiLogin(identifier, password);
      tokenStorage.setTokens(data.access, data.refresh);
      hasBootstrapped = true;
      set({
        user: data.user,
        accessToken: data.access,
        isAuthenticated: true,
        isLoading: false,
        hasHydrated: true,
        isHydrating: false,
        sessionExpired: false,
      });
    } catch (err) {
      set({ isLoading: false });
      throw err; // component handles the error message
    }
  },

  logout: async () => {
    const refresh = tokenStorage.getRefresh();
    try {
      if (refresh) await apiLogout(refresh);
    } finally {
      hasBootstrapped = true;
      get().clearSession(false);
    }
  },
}));
