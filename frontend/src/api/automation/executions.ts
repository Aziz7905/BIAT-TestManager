import apiClient from "../client";
import type {
  CreateExecutionPayload,
  ExecutionCheckpoint,
  ExecutionStep,
  ExecutionStreamTicket,
  StartManualBrowserPayload,
  TestExecution,
  TestResult,
} from "../../types/automation";

export async function getExecutions(filters?: {
  project?: string;
  suite?: string;
  test_case?: string;
  status?: string;
  trigger_type?: string;
  include_diagnostic?: boolean;
}): Promise<TestExecution[]> {
  const { data } = await apiClient.get("/test-executions/", { params: filters });
  return data.results ?? data;
}

export async function getExecution(id: string): Promise<TestExecution> {
  const { data } = await apiClient.get(`/test-executions/${id}/`);
  return data;
}

export async function createExecution(payload: CreateExecutionPayload): Promise<TestExecution> {
  const { data } = await apiClient.post("/test-executions/", payload);
  return data;
}

export async function startManualBrowser(
  payload: StartManualBrowserPayload,
): Promise<TestExecution> {
  const { data } = await apiClient.post("/test-executions/manual-browser/", payload);
  return data;
}

export async function deleteExecution(id: string): Promise<void> {
  await apiClient.delete(`/test-executions/${id}/`);
}

export async function pauseExecution(id: string): Promise<TestExecution> {
  const { data } = await apiClient.post(`/test-executions/${id}/pause/`);
  return data;
}

export async function resumeExecution(id: string): Promise<TestExecution> {
  const { data } = await apiClient.post(`/test-executions/${id}/resume/`);
  return data;
}

export async function stopExecution(id: string): Promise<TestExecution> {
  const { data } = await apiClient.post(`/test-executions/${id}/stop/`);
  return data;
}

export async function getStreamTicket(id: string): Promise<ExecutionStreamTicket> {
  const { data } = await apiClient.post(`/test-executions/${id}/stream-ticket/`);
  return data;
}

export async function getExecutionSteps(executionId: string): Promise<ExecutionStep[]> {
  const { data } = await apiClient.get(`/test-executions/${executionId}/steps/`);
  return data.results ?? data;
}

export async function getExecutionResult(executionId: string): Promise<TestResult> {
  const { data } = await apiClient.get(`/test-executions/${executionId}/result/`);
  return data;
}

export async function resumeCheckpoint(
  executionId: string,
  checkpointId: string,
  payload?: Record<string, unknown>,
): Promise<ExecutionCheckpoint> {
  const { data } = await apiClient.post(
    `/test-executions/${executionId}/checkpoints/${checkpointId}/resume/`,
    payload ?? {},
  );
  return data;
}
