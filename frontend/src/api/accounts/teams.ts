import apiClient from "../client";
import type {
  AddMemberPayload,
  PaginatedResponse,
  Team,
  TeamMember,
  CreateTeamPayload,
  UpdateMemberPayload,
  UpdateTeamPayload,
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

export async function getTeamsPage(page = 1): Promise<PaginatedResponse<Team>> {
  const { data } = await apiClient.get<PaginatedResponse<Team> | Team[]>("/teams/", {
    params: { page },
  });
  return toPaginatedResponse(data);
}

export async function getTeams(): Promise<Team[]> {
  return (await getTeamsPage()).results;
}

export async function getAllTeams(): Promise<Team[]> {
  const teams: Team[] = [];
  let page = 1;

  while (true) {
    const response = await getTeamsPage(page);
    teams.push(...response.results);
    if (!response.next) {
      break;
    }
    page += 1;
  }

  return teams;
}

export async function createTeam(payload: CreateTeamPayload): Promise<Team> {
  const { data } = await apiClient.post<Team>("/teams/", payload);
  return data;
}

export async function updateTeam(id: string, payload: UpdateTeamPayload): Promise<Team> {
  const { data } = await apiClient.patch<Team>(`/teams/${id}/`, payload);
  return data;
}

export async function deleteTeam(id: string): Promise<void> {
  await apiClient.delete(`/teams/${id}/`);
}

export async function getTeamMembersPage(
  teamId: string,
  page = 1
): Promise<PaginatedResponse<TeamMember>> {
  const { data } = await apiClient.get<PaginatedResponse<TeamMember> | TeamMember[]>(
    `/teams/${teamId}/members/`,
    { params: { page } }
  );
  return toPaginatedResponse(data);
}

export async function getTeamMembers(teamId: string): Promise<TeamMember[]> {
  return (await getTeamMembersPage(teamId)).results;
}

export async function addTeamMember(teamId: string, payload: AddMemberPayload): Promise<TeamMember> {
  const { data } = await apiClient.post<TeamMember>(`/teams/${teamId}/members/`, payload);
  return data;
}

export async function updateTeamMember(
  teamId: string,
  membershipId: string,
  payload: UpdateMemberPayload
): Promise<TeamMember> {
  const { data } = await apiClient.patch<TeamMember>(
    `/teams/${teamId}/members/${membershipId}/`,
    payload
  );
  return data;
}

export async function removeTeamMember(teamId: string, membershipId: string): Promise<void> {
  await apiClient.delete(`/teams/${teamId}/members/${membershipId}/`);
}
