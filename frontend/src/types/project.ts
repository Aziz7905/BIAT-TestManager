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
  created_by: number;
  created_by_name: string;
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
  user_role: string;
  role: ProjectMemberRole;
  joined_at: string;
}
