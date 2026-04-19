import apiClient from "../client";
import type { Project, ProjectMember, ProjectMemberRole } from "../../types/project";
import type { ProjectTree } from "../../types/testing";

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export async function getProjects(status?: string): Promise<Project[]> {
  const params = status ? { status } : {};
  const { data } = await apiClient.get<PaginatedResponse<Project> | Project[]>("/projects/", { params });
  return Array.isArray(data) ? data : data.results;
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await apiClient.get<Project>(`/projects/${id}/`);
  return data;
}

export async function createProject(payload: {
  team: string;
  name: string;
  description?: string;
}): Promise<Project> {
  const { data } = await apiClient.post<Project>("/projects/", payload);
  return data;
}

export async function updateProject(
  id: string,
  payload: Partial<{ name: string; description: string }>
): Promise<Project> {
  const { data } = await apiClient.patch<Project>(`/projects/${id}/`, payload);
  return data;
}

export async function archiveProject(id: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${id}/archive/`);
  return data;
}

export async function restoreProject(id: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${id}/restore/`);
  return data;
}

export async function getProjectTree(id: string): Promise<ProjectTree> {
  const { data } = await apiClient.get<ProjectTree>(`/projects/${id}/tree/`);
  return data;
}

// Members
export async function getProjectMembers(projectId: string): Promise<ProjectMember[]> {
  const { data } = await apiClient.get<PaginatedResponse<ProjectMember> | ProjectMember[]>(
    `/projects/${projectId}/members/`
  );
  return Array.isArray(data) ? data : data.results;
}

export async function addProjectMember(
  projectId: string,
  payload: { user: number; role: ProjectMemberRole }
): Promise<ProjectMember> {
  const { data } = await apiClient.post<ProjectMember>(
    `/projects/${projectId}/members/`,
    payload
  );
  return data;
}

export async function updateProjectMember(
  projectId: string,
  membershipId: string,
  role: ProjectMemberRole
): Promise<ProjectMember> {
  const { data } = await apiClient.patch<ProjectMember>(
    `/projects/${projectId}/members/${membershipId}/`,
    { role }
  );
  return data;
}

export async function removeProjectMember(
  projectId: string,
  membershipId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/members/${membershipId}/`);
}
