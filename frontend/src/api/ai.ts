import apiClient from "./client";
import type {
  AIGenerationSession,
  CommitAIGenerationResponse,
  ReviewAIGenerationPayload,
  StartAIGenerationPayload,
} from "../types/ai";

export async function startAIGeneration(
  payload: StartAIGenerationPayload
): Promise<AIGenerationSession> {
  const { data } = await apiClient.post<AIGenerationSession>("/ai/generations/", payload);
  return data;
}

export async function getAIGenerationSession(sessionId: string): Promise<AIGenerationSession> {
  const { data } = await apiClient.get<AIGenerationSession>(`/ai/generations/${sessionId}/`);
  return data;
}

export async function updateAIGenerationReview(
  sessionId: string,
  payload: ReviewAIGenerationPayload
): Promise<AIGenerationSession> {
  const { data } = await apiClient.patch<AIGenerationSession>(
    `/ai/generations/${sessionId}/review/`,
    payload
  );
  return data;
}

export async function commitAIGeneration(
  sessionId: string,
  createAsApproved = false
): Promise<CommitAIGenerationResponse> {
  const { data } = await apiClient.post<CommitAIGenerationResponse>(
    `/ai/generations/${sessionId}/commit/`,
    { create_as_approved: createAsApproved }
  );
  return data;
}
