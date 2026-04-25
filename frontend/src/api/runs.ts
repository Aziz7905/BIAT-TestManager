import apiClient from "./client";
import type { PaginatedResponse } from "../types/common";
import type {
  CreateTestPlanPayload,
  CreateTestRunPayload,
  ExpandRunPayload,
  TestPlan,
  TestRun,
  TestRunCase,
  TestRunCaseStatus,
} from "../types/runs";

function normalizePage<T>(data: PaginatedResponse<T> | T[]): PaginatedResponse<T> {
  if (Array.isArray(data)) {
    return {
      count: data.length,
      next: null,
      previous: null,
      results: data,
    };
  }
  return data;
}

export async function getTestPlans(projectId: string, page = 1): Promise<PaginatedResponse<TestPlan>> {
  const { data } = await apiClient.get("/test-plans/", {
    params: { project: projectId, page },
  });
  return normalizePage<TestPlan>(data);
}

export async function createTestPlan(payload: CreateTestPlanPayload): Promise<TestPlan> {
  const { data } = await apiClient.post("/test-plans/", payload);
  return data;
}

export async function getTestRuns(filters: {
  project?: string;
  plan?: string;
  page?: number;
}): Promise<PaginatedResponse<TestRun>> {
  const { data } = await apiClient.get("/test-runs/", { params: filters });
  return normalizePage<TestRun>(data);
}

export async function createTestRun(payload: CreateTestRunPayload): Promise<TestRun> {
  const { data } = await apiClient.post("/test-runs/", payload);
  return data;
}

export async function getPlanRuns(planId: string): Promise<TestRun[]> {
  const { data } = await apiClient.get(`/test-plans/${planId}/runs/`);
  return Array.isArray(data) ? data : data.results;
}

export async function startTestRun(runId: string): Promise<TestRun> {
  const { data } = await apiClient.post(`/test-runs/${runId}/start/`);
  return data;
}

export async function closeTestRun(runId: string): Promise<TestRun> {
  const { data } = await apiClient.post(`/test-runs/${runId}/close/`);
  return data;
}

export async function expandTestRun(runId: string, payload: ExpandRunPayload) {
  const { data } = await apiClient.post(`/test-runs/${runId}/expand/`, payload);
  return data;
}

export async function getRunCases(runId: string): Promise<TestRunCase[]> {
  const { data } = await apiClient.get(`/test-runs/${runId}/cases/`);
  return Array.isArray(data) ? data : data.results;
}

export async function updateRunCaseStatus(
  runCaseId: string,
  status: TestRunCaseStatus
): Promise<TestRunCase> {
  const { data } = await apiClient.patch(`/test-run-cases/${runCaseId}/`, { status });
  return data;
}

export async function executeRunCase(
  runCaseId: string,
  options: { browser?: string; platform?: string } = {}
): Promise<TestRunCase> {
  const { data } = await apiClient.post(`/test-run-cases/${runCaseId}/execute/`, options);
  return data;
}
