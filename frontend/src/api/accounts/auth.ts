import apiClient from "../client";
import type { LoginResponse, User } from "../../types/auth";

export async function login(identifier: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/login/", { identifier, password });
  return data;
}

export async function logout(refresh: string): Promise<void> {
  await apiClient.post("/logout/", { refresh });
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/me/");
  return data;
}
