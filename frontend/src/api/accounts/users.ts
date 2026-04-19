import apiClient from "../client";
import type {
  AdminUser,
  CreateUserPayload,
  PaginatedResponse,
  UpdateUserPayload,
} from "../../types/accounts";

function toPaginatedResponse<T>(data: PaginatedResponse<T> | T[]): PaginatedResponse<T> {
  if (Array.isArray(data)) {
    return {
      count: data.length,
      next: null,
      previous: null,
      results: data,
    };
  }

  return data;
}

export async function getUsersPage(page = 1): Promise<PaginatedResponse<AdminUser>> {
  const { data } = await apiClient.get<PaginatedResponse<AdminUser> | AdminUser[]>("/admin/users/", {
    params: { page },
  });
  return toPaginatedResponse(data);
}

export async function getUsers(): Promise<AdminUser[]> {
  return (await getUsersPage()).results;
}

export async function getAllUsers(): Promise<AdminUser[]> {
  const users: AdminUser[] = [];
  let page = 1;

  while (true) {
    const response = await getUsersPage(page);
    users.push(...response.results);
    if (!response.next) {
      break;
    }
    page += 1;
  }

  return users;
}

export async function createUser(payload: CreateUserPayload): Promise<AdminUser> {
  const { data } = await apiClient.post<AdminUser>("/admin/users/", payload);
  return data;
}

export async function updateUser(id: number, payload: UpdateUserPayload): Promise<AdminUser> {
  const { data } = await apiClient.patch<AdminUser>(`/admin/users/${id}/`, payload);
  return data;
}

export async function deleteUser(id: number): Promise<void> {
  await apiClient.delete(`/admin/users/${id}/`);
}
