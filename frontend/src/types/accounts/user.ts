import type { UserProfile, UserProfileRole } from "./profile";

export interface CurrentUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  profile: UserProfile;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  profile: UserProfile;
  date_joined: string;
}

export interface AdminCreateUserPayload {
  first_name: string;
  last_name: string;
  password: string;
  team?: string;
  role?: UserProfileRole;
  is_staff?: boolean;
}

export interface AdminUpdateUserPayload {
  first_name?: string;
  last_name?: string;
  team?: string;
  role?: UserProfileRole;
  is_staff?: boolean;
  password?: string;
}
