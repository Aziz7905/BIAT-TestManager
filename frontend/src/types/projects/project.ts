import type { UserProfileRole } from "../accounts";

export type ProjectStatus = "active" | "archived";
export type ProjectMemberRole = "owner" | "editor" | "viewer";

export interface Project {
  id: string;
  team: string;
  team_name: string;
  organization: string;
  organization_name: string;
  name: string;
  description: string;
  status: ProjectStatus;
  created_by: number | null;
  created_by_name: string | null;
  member_names: string[];
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectMember {
  id: string;
  user_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  user_role: UserProfileRole;
  role: ProjectMemberRole;
  joined_at: string;
}

export interface ProjectCreatePayload {
  team: string;
  name: string;
  description?: string;
  status?: ProjectStatus;
}

export interface ProjectUpdatePayload {
  team?: string;
  name?: string;
  description?: string;
  status?: ProjectStatus;
}

export interface ProjectMemberCreatePayload {
  user: number;
  role: ProjectMemberRole;
}

export interface ProjectMemberUpdatePayload {
  role: ProjectMemberRole;
}
