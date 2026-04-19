import apiClient from "../client";
import type { MyProfile, UpdateProfilePayload } from "../../types/accounts";

export async function getMyProfile(): Promise<MyProfile> {
  const { data } = await apiClient.get<MyProfile>("/profile/");
  return data;
}

export async function updateMyProfile(payload: UpdateProfilePayload): Promise<MyProfile> {
  const { data } = await apiClient.patch<MyProfile>("/profile/", payload);
  return data;
}

export async function changeMyPassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await apiClient.post("/profile/change-password/", payload);
}
