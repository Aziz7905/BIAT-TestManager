export type UserProfileRole =
  | "platform_owner"
  | "org_admin"
  | "team_manager"
  | "tester"
  | "viewer";

export type TeamMembershipRole = "manager" | "tester" | "viewer";

export type NotificationProvider = "none" | "slack" | "teams";

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

export interface UserProfile {
  id: string;
  organization: string;
  organization_name: string;
  team: string | null;
  team_name: string | null;
  team_memberships: TeamMembershipSummary[];
  role: UserProfileRole;
  notification_provider: NotificationProvider;
  notifications_enabled: boolean;
  created_at: string;
}

export interface MyProfile {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  organization: string;
  organization_name: string;
  team: string | null;
  team_name: string | null;
  team_memberships: TeamMembershipSummary[];
  role: UserProfileRole;
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

export interface UpdateMyProfilePayload {
  first_name?: string;
  last_name?: string;
  jira_token?: string | null;
  github_token?: string | null;
  notification_provider?: NotificationProvider;
  slack_user_id?: string | null;
  slack_username?: string | null;
  teams_user_id?: string | null;
  notifications_enabled?: boolean;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_new_password: string;
}
