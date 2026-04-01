import { apiClient } from "../client";
import type { Organization, OrganizationFormData } from "../../types/accounts";

export const getOrganizations = async (): Promise<Organization[]> => {
  const response = await apiClient.get<Organization[]>("/organizations/");
  return response.data;
};

export const getOrganizationById = async (organizationId: string): Promise<Organization> => {
  const response = await apiClient.get<Organization>(`/organizations/${organizationId}/`);
  return response.data;
};

export const createOrganization = async (
  payload: Omit<OrganizationFormData, "logo">
): Promise<Organization> => {
  const response = await apiClient.post<Organization>("/organizations/", payload);
  return response.data;
};

export const updateOrganization = async (
  organizationId: string,
  payload: Partial<Omit<OrganizationFormData, "logo">>
): Promise<Organization> => {
  const response = await apiClient.patch<Organization>(
    `/organizations/${organizationId}/`,
    payload
  );
  return response.data;
};

export const deleteOrganization = async (organizationId: string): Promise<void> => {
  await apiClient.delete(`/organizations/${organizationId}/`);
};