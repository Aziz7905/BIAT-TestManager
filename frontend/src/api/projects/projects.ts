import { apiClient } from "../client";
import type {
  Project,
  ProjectCreatePayload,
  ProjectMember,
  ProjectMemberCreatePayload,
  ProjectMemberUpdatePayload,
  ProjectUpdatePayload,
} from "../../types/projects";

export const getProjects = async (): Promise<Project[]> => {
  const response = await apiClient.get<Project[]>("/projects/");
  return response.data;
};

export const createProject = async (
  payload: ProjectCreatePayload
): Promise<Project> => {
  const response = await apiClient.post<Project>("/projects/", payload);
  return response.data;
};

export const updateProject = async (
  projectId: string,
  payload: ProjectUpdatePayload
): Promise<Project> => {
  const response = await apiClient.patch<Project>(`/projects/${projectId}/`, payload);
  return response.data;
};

export const deleteProject = async (projectId: string): Promise<void> => {
  await apiClient.delete(`/projects/${projectId}/`);
};

export const getProjectMembers = async (
  projectId: string
): Promise<ProjectMember[]> => {
  const response = await apiClient.get<ProjectMember[]>(
    `/projects/${projectId}/members/`
  );
  return response.data;
};

export const addProjectMember = async (
  projectId: string,
  payload: ProjectMemberCreatePayload
): Promise<ProjectMember> => {
  const response = await apiClient.post<ProjectMember>(
    `/projects/${projectId}/members/`,
    payload
  );
  return response.data;
};

export const updateProjectMember = async (
  projectId: string,
  membershipId: string,
  payload: ProjectMemberUpdatePayload
): Promise<ProjectMember> => {
  const response = await apiClient.patch<ProjectMember>(
    `/projects/${projectId}/members/${membershipId}/`,
    payload
  );
  return response.data;
};

export const removeProjectMember = async (
  projectId: string,
  membershipId: string
): Promise<void> => {
  await apiClient.delete(`/projects/${projectId}/members/${membershipId}/`);
};
