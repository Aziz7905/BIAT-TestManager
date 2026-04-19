import apiClient from "./client";
import type { PaginatedResponse } from "../types/common";
import type {
  CreateSpecificationSourcePayload,
  ImportSpecificationSourceResponse,
  SpecificationDetail,
  SpecificationListItem,
  SpecificationSourceDetail,
  SpecificationSourceListItem,
  UpdateSpecificationSourcePayload,
  UpdateSpecificationSourceRecordPayload,
} from "../types/specs";

function toPaginatedResponse<T>(data: PaginatedResponse<T> | T[]): PaginatedResponse<T> {
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

function appendFormValue(
  formData: FormData,
  key: string,
  value: string | boolean | File | null | undefined
) {
  if (value === undefined || value === null || value === "") return;
  if (value instanceof File) {
    formData.append(key, value);
    return;
  }
  if (typeof value === "boolean") {
    formData.append(key, value ? "true" : "false");
    return;
  }
  formData.append(key, value);
}

export async function getSpecificationSourcesPage(
  projectId: string,
  page = 1
): Promise<PaginatedResponse<SpecificationSourceListItem>> {
  const { data } = await apiClient.get<
    PaginatedResponse<SpecificationSourceListItem> | SpecificationSourceListItem[]
  >("/specification-sources/", {
    params: { project: projectId, page },
  });
  return toPaginatedResponse(data);
}

export async function createSpecificationSource(
  payload: CreateSpecificationSourcePayload
): Promise<SpecificationSourceDetail> {
  const formData = new FormData();
  appendFormValue(formData, "project", payload.project);
  appendFormValue(formData, "name", payload.name);
  appendFormValue(formData, "source_type", payload.source_type);
  appendFormValue(formData, "file", payload.file);
  appendFormValue(formData, "raw_text", payload.raw_text);
  appendFormValue(formData, "source_url", payload.source_url);
  appendFormValue(formData, "jira_issue_key", payload.jira_issue_key);
  appendFormValue(formData, "auto_parse", payload.auto_parse ?? true);
  appendFormValue(formData, "auto_import", payload.auto_import ?? false);

  const { data } = await apiClient.post<SpecificationSourceDetail>(
    "/specification-sources/",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    }
  );
  return data;
}

export async function getSpecificationSourceDetail(
  sourceId: string
): Promise<SpecificationSourceDetail> {
  const { data } = await apiClient.get<SpecificationSourceDetail>(
    `/specification-sources/${sourceId}/`
  );
  return data;
}

export async function parseSpecificationSource(
  sourceId: string
): Promise<SpecificationSourceDetail> {
  const { data } = await apiClient.post<SpecificationSourceDetail>(
    `/specification-sources/${sourceId}/parse/`
  );
  return data;
}

export async function importSpecificationSource(
  sourceId: string
): Promise<ImportSpecificationSourceResponse> {
  const { data } = await apiClient.post<ImportSpecificationSourceResponse>(
    `/specification-sources/${sourceId}/import/`
  );
  return data;
}

export async function deleteSelectedSpecificationSourceRecords(sourceId: string): Promise<number> {
  const { data } = await apiClient.delete<{ deleted_count: number }>(
    `/specification-sources/${sourceId}/records/selected/`
  );
  return data.deleted_count;
}

export async function updateSpecificationSource(
  sourceId: string,
  payload: UpdateSpecificationSourcePayload
): Promise<SpecificationSourceDetail> {
  const { data } = await apiClient.patch<SpecificationSourceDetail>(
    `/specification-sources/${sourceId}/`,
    payload
  );
  return data;
}

export async function deleteSpecificationSource(sourceId: string): Promise<void> {
  await apiClient.delete(`/specification-sources/${sourceId}/`);
}

export async function updateSpecificationSourceRecord(
  sourceId: string,
  recordId: string,
  payload: UpdateSpecificationSourceRecordPayload
): Promise<void> {
  await apiClient.patch(`/specification-sources/${sourceId}/records/${recordId}/`, payload);
}

export async function getSpecificationsPage(
  projectId: string,
  page = 1
): Promise<PaginatedResponse<SpecificationListItem>> {
  const { data } = await apiClient.get<
    PaginatedResponse<SpecificationListItem> | SpecificationListItem[]
  >("/specifications/", {
    params: { project: projectId, page },
  });
  return toPaginatedResponse(data);
}

export async function getSpecificationDetail(specId: string): Promise<SpecificationDetail> {
  const { data } = await apiClient.get<SpecificationDetail>(`/specifications/${specId}/`);
  return data;
}

export async function deleteSpecification(specId: string): Promise<void> {
  await apiClient.delete(`/specifications/${specId}/`);
}
