import type { TeamMembershipRole, UserProfileRole } from "./profile";

export interface Team {
  id: string;
  organization: string;
  organization_name: string;
  name: string;
  manager: number | null;
  manager_name: string | null;
  member_names: string[];
  member_count: number;
  ai_provider: number | null;
  ai_provider_name: string | null;
  has_ai_api_key: boolean;
  ai_model: string;
  monthly_token_budget: number;
  tokens_used_this_month: number;
  jira_base_url: string | null;
  jira_project_key: string | null;
  github_org: string | null;
  github_repo: string | null;
  jenkins_url: string | null;
  created_at: string;
}

export interface TeamMember {
  id: string;
  user_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  user_role: UserProfileRole;
  role: TeamMembershipRole;
  is_primary: boolean;
  is_active: boolean;
  joined_at: string;
}

export interface TeamMemberCreatePayload {
  user: number;
  role?: TeamMembershipRole;
  is_primary?: boolean;
}

export interface TeamMemberUpdatePayload {
  role?: TeamMembershipRole;
  is_primary?: boolean;
}

export interface TeamCreatePayload {
  organization?: string;
  name: string;
  manager?: number | null;
  ai_provider?: number | null;
  ai_api_key?: string | null;
  ai_model?: string;
  monthly_token_budget?: number;
  jira_base_url?: string | null;
  jira_project_key?: string | null;
  github_org?: string | null;
  github_repo?: string | null;
  jenkins_url?: string | null;
}

export interface TeamUpdatePayload {
  organization?: string;
  name?: string;
  manager?: number | null;
  ai_provider?: number | null;
  ai_api_key?: string | null;
  ai_model?: string;
  monthly_token_budget?: number;
  jira_base_url?: string | null;
  jira_project_key?: string | null;
  github_org?: string | null;
  github_repo?: string | null;
  jenkins_url?: string | null;
}
