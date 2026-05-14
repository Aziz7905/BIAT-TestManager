import apiClient from "./client";
import type {
  AIGenerationSession,
  CommitAIGenerationResponse,
  ReviewAIGenerationPayload,
  SaveAIAuthoringTraceResponse,
  StartAIAuthoringSessionPayload,
  StartAIGenerationPayload,
} from "../types/ai";
import type { TestExecution } from "../types/automation";

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

export async function startAIAuthoringSession(
  payload: StartAIAuthoringSessionPayload
): Promise<TestExecution> {
  const { data } = await apiClient.post<TestExecution>("/ai/authoring/sessions/", payload);
  return data;
}

export async function saveAIAuthoringTrace(
  executionId: string
): Promise<SaveAIAuthoringTraceResponse> {
  const { data } = await apiClient.post<SaveAIAuthoringTraceResponse>(
    `/ai/authoring/sessions/${executionId}/save-trace/`,
    {}
  );
  return data;
}
