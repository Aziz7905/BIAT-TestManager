/** Client helpers for the BIAT Test Manager automation backend endpoints. */
import { apiClient } from "../client";
import type {
  AutomationScript,
  AutomationScriptWritePayload,
  ExecutionStep,
  ScriptValidationResult,
  TestExecution,
  TestExecutionCreatePayload,
} from "../../types/automation";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";
const MEDIA_BASE_URL = new URL("/media/", API_BASE_URL).toString();

interface GetAutomationScriptsParams {
  test_case?: string;
}

interface GetTestExecutionsParams {
  project?: string;
  suite?: string;
  test_case?: string;
  status?: string;
}

export const getAutomationScripts = async (
  params?: GetAutomationScriptsParams
): Promise<AutomationScript[]> => {
  const response = await apiClient.get<AutomationScript[]>("/automation-scripts/", {
    params,
  });
  return response.data;
};

export const getAutomationScript = async (
  scriptId: string
): Promise<AutomationScript> => {
  const response = await apiClient.get<AutomationScript>(
    `/automation-scripts/${scriptId}/`
  );
  return response.data;
};

export const createAutomationScript = async (
  payload: AutomationScriptWritePayload
): Promise<AutomationScript> => {
  const response = await apiClient.post<AutomationScript>(
    "/automation-scripts/",
    payload
  );
  return response.data;
};

export const updateAutomationScript = async (
  scriptId: string,
  payload: Partial<AutomationScriptWritePayload>
): Promise<AutomationScript> => {
  const response = await apiClient.patch<AutomationScript>(
    `/automation-scripts/${scriptId}/`,
    payload
  );
  return response.data;
};

export const deleteAutomationScript = async (scriptId: string): Promise<void> => {
  await apiClient.delete(`/automation-scripts/${scriptId}/`);
};

export const activateAutomationScript = async (
  scriptId: string
): Promise<AutomationScript> => {
  const response = await apiClient.post<AutomationScript>(
    `/automation-scripts/${scriptId}/activate/`
  );
  return response.data;
};

export const deactivateAutomationScript = async (
  scriptId: string
): Promise<AutomationScript> => {
  const response = await apiClient.post<AutomationScript>(
    `/automation-scripts/${scriptId}/deactivate/`
  );
  return response.data;
};

export const validateAutomationScript = async (
  scriptId: string
): Promise<ScriptValidationResult> => {
  const response = await apiClient.post<ScriptValidationResult>(
    `/automation-scripts/${scriptId}/validate/`
  );
  return response.data;
};

export const getTestExecutions = async (
  params?: GetTestExecutionsParams
): Promise<TestExecution[]> => {
  const response = await apiClient.get<TestExecution[]>("/test-executions/", {
    params,
  });
  return response.data;
};

export const createTestExecution = async (
  payload: TestExecutionCreatePayload
): Promise<TestExecution> => {
  const response = await apiClient.post<TestExecution>("/test-executions/", payload);
  return response.data;
};

export const getExecutionSteps = async (
  executionId: string
): Promise<ExecutionStep[]> => {
  const response = await apiClient.get<ExecutionStep[]>(
    `/test-executions/${executionId}/steps/`
  );
  return response.data;
};

export const getExecutionArtifactText = async (
  executionId: string,
  fileName: "stdout.log" | "stderr.log"
): Promise<string> => {
  try {
    const response = await fetch(
      `${MEDIA_BASE_URL}automation_artifacts/${executionId}/${fileName}?t=${Date.now()}`
    );
    if (!response.ok) {
      return "";
    }
    return await response.text();
  } catch {
    return "";
  }
};

export const resolveExecutionArtifactUrl = (
  artifactPath: string | null | undefined
): string | null => {
  if (!artifactPath) {
    return null;
  }

  if (artifactPath.startsWith("http://") || artifactPath.startsWith("https://")) {
    return artifactPath;
  }

  return new URL(artifactPath, MEDIA_BASE_URL).toString();
};

export const pauseTestExecution = async (
  executionId: string
): Promise<TestExecution> => {
  const response = await apiClient.post<TestExecution>(
    `/test-executions/${executionId}/pause/`
  );
  return response.data;
};

export const resumeTestExecution = async (
  executionId: string
): Promise<TestExecution> => {
  const response = await apiClient.post<TestExecution>(
    `/test-executions/${executionId}/resume/`
  );
  return response.data;
};

export const stopTestExecution = async (
  executionId: string
): Promise<TestExecution> => {
  const response = await apiClient.post<TestExecution>(
    `/test-executions/${executionId}/stop/`
  );
  return response.data;
};

export const deleteTestExecution = async (executionId: string): Promise<void> => {
  await apiClient.delete(`/test-executions/${executionId}/`);
};
