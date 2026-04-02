/** Client helpers for the BIAT Test Manager testing backend endpoints. */
import { apiClient } from "../client";
import type {
  TestCase,
  TestCaseWritePayload,
  TestScenario,
  TestScenarioCreatePayload,
  TestScenarioUpdatePayload,
  TestSuite,
  TestSuiteCreatePayload,
  TestSuiteUpdatePayload,
} from "../../types/testing";

interface GetTestSuitesParams {
  project?: string;
  specification?: string;
}

export const getTestSuites = async (
  params?: GetTestSuitesParams
): Promise<TestSuite[]> => {
  const response = await apiClient.get<TestSuite[]>("/test-suites/", {
    params,
  });
  return response.data;
};

export const getTestSuite = async (suiteId: string): Promise<TestSuite> => {
  const response = await apiClient.get<TestSuite>(`/test-suites/${suiteId}/`);
  return response.data;
};

export const createTestSuite = async (
  payload: TestSuiteCreatePayload
): Promise<TestSuite> => {
  const response = await apiClient.post<TestSuite>("/test-suites/", payload);
  return response.data;
};

export const updateTestSuite = async (
  suiteId: string,
  payload: TestSuiteUpdatePayload
): Promise<TestSuite> => {
  const response = await apiClient.patch<TestSuite>(
    `/test-suites/${suiteId}/`,
    payload
  );
  return response.data;
};

export const deleteTestSuite = async (suiteId: string): Promise<void> => {
  await apiClient.delete(`/test-suites/${suiteId}/`);
};

export const getTestScenarios = async (
  suiteId: string
): Promise<TestScenario[]> => {
  const response = await apiClient.get<TestScenario[]>(
    `/test-suites/${suiteId}/scenarios/`
  );
  return response.data;
};

export const createTestScenario = async (
  suiteId: string,
  payload: TestScenarioCreatePayload
): Promise<TestScenario> => {
  const response = await apiClient.post<TestScenario>(
    `/test-suites/${suiteId}/scenarios/`,
    payload
  );
  return response.data;
};

export const updateTestScenario = async (
  suiteId: string,
  scenarioId: string,
  payload: TestScenarioUpdatePayload
): Promise<TestScenario> => {
  const response = await apiClient.patch<TestScenario>(
    `/test-suites/${suiteId}/scenarios/${scenarioId}/`,
    payload
  );
  return response.data;
};

export const deleteTestScenario = async (
  suiteId: string,
  scenarioId: string
): Promise<void> => {
  await apiClient.delete(`/test-suites/${suiteId}/scenarios/${scenarioId}/`);
};

export const cloneTestScenario = async (
  scenarioId: string
): Promise<TestScenario> => {
  const response = await apiClient.post<TestScenario>(
    `/test-scenarios/${scenarioId}/clone/`
  );
  return response.data;
};

export const getTestCases = async (
  scenarioId: string
): Promise<TestCase[]> => {
  const response = await apiClient.get<TestCase[]>(
    `/test-scenarios/${scenarioId}/cases/`
  );
  return response.data;
};

export const createTestCase = async (
  scenarioId: string,
  payload: TestCaseWritePayload
): Promise<TestCase> => {
  const response = await apiClient.post<TestCase>(
    `/test-scenarios/${scenarioId}/cases/`,
    payload
  );
  return response.data;
};

export const updateTestCase = async (
  scenarioId: string,
  caseId: string,
  payload: TestCaseWritePayload
): Promise<TestCase> => {
  const response = await apiClient.patch<TestCase>(
    `/test-scenarios/${scenarioId}/cases/${caseId}/`,
    payload
  );
  return response.data;
};

export const deleteTestCase = async (
  scenarioId: string,
  caseId: string
): Promise<void> => {
  await apiClient.delete(`/test-scenarios/${scenarioId}/cases/${caseId}/`);
};
