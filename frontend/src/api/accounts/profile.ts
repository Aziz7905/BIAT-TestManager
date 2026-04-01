import { apiClient } from "../client";
import type {
  ChangePasswordPayload,
  MyProfile,
  UpdateMyProfilePayload,
} from "../../types/accounts";

interface ChangePasswordResponse {
  detail: string;
}

export const getMyProfile = async (): Promise<MyProfile> => {
  const response = await apiClient.get<MyProfile>("/profile/");
  return response.data;
};

export const updateMyProfile = async (
  payload: UpdateMyProfilePayload
): Promise<MyProfile> => {
  const response = await apiClient.patch<MyProfile>("/profile/", payload);
  return response.data;
};

export const changeMyPassword = async (
  payload: ChangePasswordPayload
): Promise<ChangePasswordResponse> => {
  const response = await apiClient.post<ChangePasswordResponse>(
    "/profile/change-password/",
    payload
  );
  return response.data;
};