import { apiClient } from "../client";
import type {
  Specification,
  SpecificationCreatePayload,
  SpecificationSource,
  SpecificationSourceCreatePayload,
  SpecificationSourceDetail,
  SpecificationSourceImportResponse,
  SpecificationSourceRecord,
  SpecificationSourceRecordUpdatePayload,
  SpecificationUpdatePayload,
} from "../../types/specs";

function buildSpecificationSourceFormData(
  payload: SpecificationSourceCreatePayload
): FormData {
  const formData = new FormData();
  formData.append("project", payload.project);
  formData.append("source_type", payload.source_type);

  if (payload.name?.trim()) {
    formData.append("name", payload.name.trim());
  }

  if (payload.file) {
    formData.append("file", payload.file);
  }

  if (payload.raw_text?.trim()) {
    formData.append("raw_text", payload.raw_text.trim());
  }

  if (payload.source_url?.trim()) {
    formData.append("source_url", payload.source_url.trim());
  }

  if (payload.jira_issue_key?.trim()) {
    formData.append("jira_issue_key", payload.jira_issue_key.trim());
  }

  formData.append("auto_parse", String(payload.auto_parse ?? true));
  return formData;
}

export const getSpecifications = async (
  projectId?: string
): Promise<Specification[]> => {
  const response = await apiClient.get<Specification[]>("/specifications/", {
    params: projectId ? { project: projectId } : undefined,
  });
  return response.data;
};

export const createSpecification = async (
  payload: SpecificationCreatePayload
): Promise<Specification> => {
  const response = await apiClient.post<Specification>("/specifications/", payload);
  return response.data;
};

export const updateSpecification = async (
  specificationId: string,
  payload: SpecificationUpdatePayload
): Promise<Specification> => {
  const response = await apiClient.patch<Specification>(
    `/specifications/${specificationId}/`,
    payload
  );
  return response.data;
};

export const deleteSpecification = async (
  specificationId: string
): Promise<void> => {
  await apiClient.delete(`/specifications/${specificationId}/`);
};

export const getSpecificationSources = async (
  projectId?: string
): Promise<SpecificationSource[]> => {
  const response = await apiClient.get<SpecificationSource[]>(
    "/specification-sources/",
    {
      params: projectId ? { project: projectId } : undefined,
    }
  );
  return response.data;
};

export const createSpecificationSource = async (
  payload: SpecificationSourceCreatePayload
): Promise<SpecificationSourceDetail> => {
  const response = await apiClient.post<SpecificationSourceDetail>(
    "/specification-sources/",
    buildSpecificationSourceFormData(payload),
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return response.data;
};

export const getSpecificationSource = async (
  sourceId: string
): Promise<SpecificationSourceDetail> => {
  const response = await apiClient.get<SpecificationSourceDetail>(
    `/specification-sources/${sourceId}/`
  );
  return response.data;
};

export const parseSpecificationSource = async (
  sourceId: string
): Promise<SpecificationSourceDetail> => {
  const response = await apiClient.post<SpecificationSourceDetail>(
    `/specification-sources/${sourceId}/parse/`
  );
  return response.data;
};

export const deleteSpecificationSource = async (sourceId: string): Promise<void> => {
  await apiClient.delete(`/specification-sources/${sourceId}/`);
};

export const getSpecificationSourceRecords = async (
  sourceId: string
): Promise<SpecificationSourceRecord[]> => {
  const response = await apiClient.get<SpecificationSourceRecord[]>(
    `/specification-sources/${sourceId}/records/`
  );
  return response.data;
};

export const updateSpecificationSourceRecord = async (
  sourceId: string,
  recordId: string,
  payload: SpecificationSourceRecordUpdatePayload
): Promise<SpecificationSourceRecord> => {
  const response = await apiClient.patch<SpecificationSourceRecord>(
    `/specification-sources/${sourceId}/records/${recordId}/`,
    payload
  );
  return response.data;
};

export const importSpecificationSource = async (
  sourceId: string
): Promise<SpecificationSourceImportResponse> => {
  const response = await apiClient.post<SpecificationSourceImportResponse>(
    `/specification-sources/${sourceId}/import/`
  );
  return response.data;
};
