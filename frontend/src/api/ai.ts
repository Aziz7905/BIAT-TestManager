import apiClient from "./client";
import type {
  AIGenerationSession,
  CommitAIGenerationResponse,
  ReviewAIGenerationPayload,
  SaveAIAuthoringTraceResponse,
  StartAIAuthoringSessionPayload,
  StartAIGenerationPayload,
} from "../types/ai";
import type { AutomationScript, TestExecution } from "../types/automation";

export async function startAIGeneration(
  payload: StartAIGenerationPayload
): Promise<AIGenerationSession> {
  const temporaryAttachments = Array.isArray(payload.temporary_attachments)
    ? payload.temporary_attachments.filter((file): file is File => file instanceof File)
    : [];

  if (temporaryAttachments.length) {
    const formData = new FormData();
    formData.append("project", payload.project);
    formData.append("objective", payload.objective);
    if (payload.source_type) formData.append("source_type", payload.source_type);
    if (payload.target_suite) formData.append("target_suite", payload.target_suite);
    if (payload.target_section) formData.append("target_section", payload.target_section);
    if (payload.attached_specification) {
      formData.append("attached_specification", payload.attached_specification);
    }
    for (const specificationId of payload.selected_specifications ?? []) {
      formData.append("selected_specifications", specificationId);
    }
    if (payload.source_refs) formData.append("source_refs", JSON.stringify(payload.source_refs));
    if (payload.jira_issue_key) formData.append("jira_issue_key", payload.jira_issue_key);
    for (const file of temporaryAttachments) {
      formData.append("temporary_attachments", file);
    }
    const { data } = await apiClient.post<AIGenerationSession>("/ai/generations/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  }

  const jsonPayload: StartAIGenerationPayload = { ...payload };
  delete jsonPayload.temporary_attachments;
  const { data } = await apiClient.post<AIGenerationSession>("/ai/generations/", jsonPayload);
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

export async function cancelAIGeneration(sessionId: string): Promise<AIGenerationSession> {
  const { data } = await apiClient.post<AIGenerationSession>(
    `/ai/generations/${sessionId}/cancel/`,
    {}
  );
  return data;
}

export async function answerAIGenerationClarification(
  sessionId: string,
  answers: string
): Promise<AIGenerationSession> {
  const { data } = await apiClient.post<AIGenerationSession>(
    `/ai/generations/${sessionId}/clarify/`,
    { answers }
  );
  return data;
}

export async function refineAIGeneration(
  sessionId: string,
  instruction: string,
  draftIds: string[] = []
): Promise<AIGenerationSession> {
  const { data } = await apiClient.post<AIGenerationSession>(
    `/ai/generations/${sessionId}/refine/`,
    { instruction, draft_ids: draftIds }
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

export async function saveAIAuthoringScript(
  executionId: string
): Promise<AutomationScript> {
  const { data } = await apiClient.post<AutomationScript>(
    `/ai/authoring/sessions/${executionId}/save-script/`,
    {}
  );
  return data;
}
