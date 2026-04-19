export type OrganizationRole = "platform_owner" | "org_admin" | "member";
export type TeamMembershipRole = "manager" | "tester" | "viewer";
export type NotificationProvider = "none" | "slack" | "teams";

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface TeamMembershipSummary {
  id: string;
  team: string;
  team_name: string;
  organization: string;
  organization_name: string;
  role: TeamMembershipRole;
  is_primary: boolean;
  is_active: boolean;
  joined_at: string;
}

export interface MyProfile {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  organization: string;
  organization_name: string;
  organization_role: OrganizationRole;
  team: string | null;
  team_name: string | null;
  team_memberships: TeamMembershipSummary[];
  has_jira_token: boolean;
  has_github_token: boolean;
  notification_provider: NotificationProvider;
  notifications_enabled: boolean;
  slack_user_id: string | null;
  slack_username: string | null;
  teams_user_id: string | null;
  has_slack_user: boolean;
  has_teams_user: boolean;
  created_at: string;
}

export interface UpdateProfilePayload {
  first_name?: string;
  last_name?: string;
  jira_token?: string;
  github_token?: string;
  notification_provider?: NotificationProvider;
  slack_user_id?: string;
  slack_username?: string;
  teams_user_id?: string;
  notifications_enabled?: boolean;
}

export interface UserProfileNested {
  id: string;
  organization: string;
  organization_name: string;
  organization_role: OrganizationRole;
  team: string | null;
  team_name: string | null;
  team_memberships: TeamMembershipSummary[];
  notification_provider: NotificationProvider;
  notifications_enabled: boolean;
  created_at: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  profile: UserProfileNested | null;
  date_joined: string;
}

export interface CreateUserPayload {
  first_name: string;
  last_name: string;
  password: string;
  team?: string;
  team_membership_role?: TeamMembershipRole;
  organization_role?: OrganizationRole;
  is_staff?: boolean;
}

export interface UpdateUserPayload {
  first_name?: string;
  last_name?: string;
  password?: string;
  team?: string | null;
  team_membership_role?: TeamMembershipRole;
  organization_role?: OrganizationRole;
  is_staff?: boolean;
}

export interface Team {
  id: string;
  organization: string;
  organization_name: string;
  name: string;
  manager: number | null;
  manager_name: string | null;
  member_names: string[];
  member_count: number;
  ai_provider: string | null;
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

export interface CreateTeamPayload {
  name: string;
  manager: number;
  ai_api_key?: string;
  ai_model?: string;
  monthly_token_budget?: number;
  jira_base_url?: string;
  jira_project_key?: string;
  github_org?: string;
  github_repo?: string;
  jenkins_url?: string;
}

export interface UpdateTeamPayload {
  name?: string;
  manager?: number;
  ai_api_key?: string;
  ai_model?: string;
  monthly_token_budget?: number;
  jira_base_url?: string;
  jira_project_key?: string;
  github_org?: string;
  github_repo?: string;
  jenkins_url?: string;
}

export interface TeamMember {
  id: string;
  user_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  user_role: OrganizationRole;
  role: TeamMembershipRole;
  is_primary: boolean;
  is_active: boolean;
  joined_at: string;
}

export interface AddMemberPayload {
  user: number;
  role?: TeamMembershipRole;
  is_primary?: boolean;
}

export interface UpdateMemberPayload {
  role?: TeamMembershipRole;
  is_primary?: boolean;
}
