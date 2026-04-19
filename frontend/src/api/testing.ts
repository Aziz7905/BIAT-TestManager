import apiClient from "./client";
import type {
  CaseWorkspace,
  CreateCasePayload,
  CreateScenarioPayload,
  CreateSectionPayload,
  CreateSuitePayload,
  ProjectRepositoryOverview,
  ScenarioOverview,
  SectionOverview,
  SuiteOverview,
  TreeCase,
} from "../types/testing";

export async function getProjectRepositoryOverview(
  projectId: string
): Promise<ProjectRepositoryOverview> {
  const { data } = await apiClient.get<ProjectRepositoryOverview>(
    `/projects/${projectId}/repository/overview/`
  );
  return data;
}

export async function getSuiteOverview(suiteId: string): Promise<SuiteOverview> {
  const { data } = await apiClient.get<SuiteOverview>(`/test-suites/${suiteId}/overview/`);
  return data;
}

export async function getSectionOverview(sectionId: string): Promise<SectionOverview> {
  const { data } = await apiClient.get<SectionOverview>(`/test-sections/${sectionId}/overview/`);
  return data;
}

export async function getScenarioOverview(scenarioId: string): Promise<ScenarioOverview> {
  const { data } = await apiClient.get<ScenarioOverview>(
    `/test-scenarios/${scenarioId}/overview/`
  );
  return data;
}

export async function getCaseWorkspace(caseId: string): Promise<CaseWorkspace> {
  const { data } = await apiClient.get<CaseWorkspace>(`/test-cases/${caseId}/workspace/`);
  return data;
}

export async function createSuite(payload: CreateSuitePayload) {
  const { data } = await apiClient.post("/test-suites/", payload);
  return data;
}

export async function updateSuite(
  suiteId: string,
  payload: Partial<CreateSuitePayload>
) {
  const { data } = await apiClient.patch(`/test-suites/${suiteId}/`, payload);
  return data;
}

export async function deleteSuite(suiteId: string) {
  await apiClient.delete(`/test-suites/${suiteId}/`);
}

export async function createSection(
  suiteId: string,
  payload: CreateSectionPayload
) {
  const { data } = await apiClient.post(`/test-suites/${suiteId}/sections/`, payload);
  return data;
}

export async function updateSection(
  suiteId: string,
  sectionId: string,
  payload: Partial<CreateSectionPayload>
) {
  const { data } = await apiClient.patch(
    `/test-suites/${suiteId}/sections/${sectionId}/`,
    payload
  );
  return data;
}

export async function deleteSection(suiteId: string, sectionId: string) {
  await apiClient.delete(`/test-suites/${suiteId}/sections/${sectionId}/`);
}

export async function createScenario(
  sectionId: string,
  payload: CreateScenarioPayload
) {
  const { data } = await apiClient.post(
    `/test-sections/${sectionId}/scenarios/`,
    payload
  );
  return data;
}

export async function updateScenario(
  sectionId: string,
  scenarioId: string,
  payload: Partial<CreateScenarioPayload>
) {
  const { data } = await apiClient.patch(
    `/test-sections/${sectionId}/scenarios/${scenarioId}/`,
    payload
  );
  return data;
}

export async function deleteScenario(sectionId: string, scenarioId: string) {
  await apiClient.delete(`/test-sections/${sectionId}/scenarios/${scenarioId}/`);
}

export async function cloneScenario(scenarioId: string) {
  const { data } = await apiClient.post(`/test-scenarios/${scenarioId}/clone/`);
  return data;
}

export async function getCasesForScenario(scenarioId: string): Promise<TreeCase[]> {
  const { data } = await apiClient.get<TreeCase[]>(`/test-scenarios/${scenarioId}/cases/`);
  return data;
}

export async function createCase(
  scenarioId: string,
  payload: CreateCasePayload
) {
  const normalizedPayload = {
    ...payload,
    test_data: payload.test_data ?? {},
    steps: payload.steps ?? [],
    timeout_ms: payload.timeout_ms ?? 120000,
  };

  const { data } = await apiClient.post(
    `/test-scenarios/${scenarioId}/cases/`,
    normalizedPayload
  );
  return data;
}

export async function updateCase(
  scenarioId: string,
  caseId: string,
  payload: Partial<CreateCasePayload>
) {
  const normalizedPayload = {
    ...payload,
    ...(payload.test_data !== undefined ? { test_data: payload.test_data } : {}),
    ...(payload.steps !== undefined ? { steps: payload.steps } : {}),
  };

  const { data } = await apiClient.patch(
    `/test-scenarios/${scenarioId}/cases/${caseId}/`,
    normalizedPayload
  );
  return data;
}

export async function deleteCase(scenarioId: string, caseId: string) {
  await apiClient.delete(`/test-scenarios/${scenarioId}/cases/${caseId}/`);
}

export async function cloneCase(caseId: string): Promise<TreeCase> {
  const { data } = await apiClient.post<TreeCase>(`/test-cases/${caseId}/clone/`);
  return data;
}
