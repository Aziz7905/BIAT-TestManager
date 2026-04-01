import { apiClient } from "../client";
import type {
  Team,
  TeamCreatePayload,
  TeamMember,
  TeamMemberCreatePayload,
  TeamMemberUpdatePayload,
  TeamUpdatePayload,
} from "../../types/accounts";

export const getTeams = async (): Promise<Team[]> => {
  const response = await apiClient.get<Team[]>("/teams/");
  return response.data;
};

export const getTeamById = async (teamId: string): Promise<Team> => {
  const response = await apiClient.get<Team>(`/teams/${teamId}/`);
  return response.data;
};

export const createTeam = async (
  payload: TeamCreatePayload
): Promise<Team> => {
  const response = await apiClient.post<Team>("/teams/", payload);
  return response.data;
};

export const updateTeam = async (
  teamId: string,
  payload: TeamUpdatePayload
): Promise<Team> => {
  const response = await apiClient.patch<Team>(`/teams/${teamId}/`, payload);
  return response.data;
};

export const deleteTeam = async (teamId: string): Promise<void> => {
  await apiClient.delete(`/teams/${teamId}/`);
};

export const getTeamMembers = async (teamId: string): Promise<TeamMember[]> => {
  const response = await apiClient.get<TeamMember[]>(`/teams/${teamId}/members/`);
  return response.data;
};

export const addTeamMember = async (
  teamId: string,
  payload: TeamMemberCreatePayload
): Promise<TeamMember> => {
  const response = await apiClient.post<TeamMember>(
    `/teams/${teamId}/members/`,
    payload
  );
  return response.data;
};

export const updateTeamMember = async (
  teamId: string,
  membershipId: string,
  payload: TeamMemberUpdatePayload
): Promise<TeamMember> => {
  const response = await apiClient.patch<TeamMember>(
    `/teams/${teamId}/members/${membershipId}/`,
    payload
  );
  return response.data;
};

export const removeTeamMember = async (
  teamId: string,
  membershipId: string
): Promise<void> => {
  await apiClient.delete(`/teams/${teamId}/members/${membershipId}/`);
};
