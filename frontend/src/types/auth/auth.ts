import type { CurrentUser } from "../accounts";

export interface LoginPayload {
  identifier: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: CurrentUser;
}

export interface RefreshTokenPayload {
  refresh: string;
}

export interface LogoutPayload {
  refresh: string;
}