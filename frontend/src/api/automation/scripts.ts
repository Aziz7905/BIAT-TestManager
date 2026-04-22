import apiClient from "../client";
import type {
  AutomationScript,
  AutomationScriptDetail,
  CreateScriptPayload,
  UpdateScriptPayload,
} from "../../types/automation";

export async function getScripts(filters?: { test_case?: string }): Promise<AutomationScript[]> {
  const { data } = await apiClient.get("/automation-scripts/", { params: filters });
  return data.results ?? data;
}

export async function getScript(id: string): Promise<AutomationScriptDetail> {
  const { data } = await apiClient.get(`/automation-scripts/${id}/`);
  return data;
}

export async function createScript(payload: CreateScriptPayload): Promise<AutomationScript> {
  const { data } = await apiClient.post("/automation-scripts/", payload);
  return data;
}

export async function updateScript(
  id: string,
  payload: UpdateScriptPayload,
): Promise<AutomationScript> {
  const { data } = await apiClient.patch(`/automation-scripts/${id}/`, payload);
  return data;
}

export async function deleteScript(id: string): Promise<void> {
  await apiClient.delete(`/automation-scripts/${id}/`);
}

export async function activateScript(id: string): Promise<AutomationScriptDetail> {
  const { data } = await apiClient.post(`/automation-scripts/${id}/activate/`);
  return data;
}

export async function deactivateScript(id: string): Promise<AutomationScriptDetail> {
  const { data } = await apiClient.post(`/automation-scripts/${id}/deactivate/`);
  return data;
}
