// src/api/auth.ts
import { apiClient } from "./client";
import type {
  LoginPayload,
  LoginResponse,
  RefreshTokenPayload,
} from "../types/auth/auth";
import type { CurrentUser } from "../types/accounts";

export const login = async (payload: LoginPayload): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>("/login/", payload);

  localStorage.setItem("access", response.data.access);
  localStorage.setItem("refresh", response.data.refresh);

  return response.data;
};

export const logout = async (): Promise<void> => {
  const refresh = localStorage.getItem("refresh");

  if (refresh) {
    await apiClient.post("/logout/", { refresh });
  }

  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
};

export const refreshToken = async (): Promise<string> => {
  const refresh = localStorage.getItem("refresh");

  if (!refresh) {
    throw new Error("No refresh token found.");
  }

  const response = await apiClient.post<{ access: string }>(
    "/refresh/",
    { refresh } as RefreshTokenPayload
  );

  localStorage.setItem("access", response.data.access);
  return response.data.access;
};

export const getCurrentUser = async (): Promise<CurrentUser> => {
  const response = await apiClient.get<CurrentUser>("/me/");
  return response.data;
};