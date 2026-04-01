import { apiClient } from "../client";
import type {
  AdminCreateUserPayload,
  AdminUpdateUserPayload,
  AdminUser,
} from "../../types/accounts";

export const getAdminUsers = async (): Promise<AdminUser[]> => {
  const response = await apiClient.get<AdminUser[]>("/admin/users/");
  return response.data;
};

export const getAdminUserById = async (userId: number): Promise<AdminUser> => {
  const response = await apiClient.get<AdminUser>(`/admin/users/${userId}/`);
  return response.data;
};

export const createAdminUser = async (
  payload: AdminCreateUserPayload
): Promise<AdminUser> => {
  const response = await apiClient.post<AdminUser>("/admin/users/", payload);
  return response.data;
};

export const updateAdminUser = async (
  userId: number,
  payload: AdminUpdateUserPayload
): Promise<AdminUser> => {
  const response = await apiClient.patch<AdminUser>(
    `/admin/users/${userId}/`,
    payload
  );
  return response.data;
};

export const deleteAdminUser = async (userId: number): Promise<void> => {
  await apiClient.delete(`/admin/users/${userId}/`);
};