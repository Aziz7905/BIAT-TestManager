import type {
  NotificationProvider,
  OrganizationRole,
  TeamMembershipSummary,
} from "./accounts";

export interface UserProfile {
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

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  profile: UserProfile;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RefreshResponse {
  access: string;
}
