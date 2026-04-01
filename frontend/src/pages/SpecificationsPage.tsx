import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { getProjects } from "../api/projects";
import {
  createSpecification,
  createSpecificationSource,
  deleteSpecification,
  deleteSpecificationSource,
  getSpecificationSource,
  getSpecificationSources,
  getSpecifications,
  importSpecificationSource,
  parseSpecificationSource,
  updateSpecification,
  updateSpecificationSourceRecord,
} from "../api/specs";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { FormSelect } from "../components/FormSelect";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import type { Project } from "../types/projects";
import type {
  Specification,
  SpecificationCreatePayload,
  SpecificationSource,
  SpecificationSourceCreatePayload,
  SpecificationSourceDetail,
  SpecificationSourceRecord,
  SpecificationSourceType,
  SpecificationUpdatePayload,
} from "../types/specs";

function readError(data: unknown): string | null {
  if (typeof data === "string" && data.trim()) return data;
  if (Array.isArray(data)) {
    for (const item of data) {
      const message = readError(item);
      if (message) return message;
    }
  }
  if (typeof data === "object" && data !== null) {
    for (const value of Object.values(data)) {
      const message = readError(value);
      if (message) return message;
    }
  }
  return null;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as { response?: { data?: unknown } }).response;
    return readError(response?.data) || fallback;
  }
  return fallback;
}

const SPEC_SOURCE_OPTIONS: Array<{
  value: SpecificationSourceType;
  label: string;
}> = [
  { value: "manual", label: "manual" },
  { value: "plain_text", label: "plain text" },
  { value: "csv", label: "csv" },
  { value: "xlsx", label: "xlsx" },
  { value: "pdf", label: "pdf" },
  { value: "docx", label: "docx" },
  { value: "jira_issue", label: "jira issue" },
  { value: "url", label: "url" },
];

const IMPORT_SOURCE_OPTIONS: Array<{
  value: SpecificationSourceType;
  label: string;
}> = [
  { value: "plain_text", label: "plain text" },
  { value: "csv", label: "csv" },
  { value: "xlsx", label: "xlsx" },
  { value: "pdf", label: "pdf" },
  { value: "docx", label: "docx" },
  { value: "jira_issue", label: "jira issue" },
  { value: "url", label: "url" },
];

const initialSpecificationForm: SpecificationCreatePayload = {
  project: "",
  title: "",
  content: "",
  source_type: "manual",
  jira_issue_key: "",
  source_url: "",
  version: "1.0",
};

const initialSourceForm = {
  project: "",
  name: "",
  source_type: "plain_text" as SpecificationSourceType,
  raw_text: "",
  source_url: "",
  jira_issue_key: "",
  file: null as File | null,
};

const labelize = (value: string) => value.replaceAll("_", " ");
const isFileSource = (value: SpecificationSourceType) =>
  value === "csv" || value === "xlsx" || value === "pdf" || value === "docx";
const hasTextArea = (value: SpecificationSourceType) =>
  value === "manual" ||
  value === "plain_text" ||
  value === "jira_issue" ||
  value === "url";

export default function SpecificationsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [specifications, setSpecifications] = useState<Specification[]>([]);
  const [sources, setSources] = useState<SpecificationSource[]>([]);
  const [filterProjectId, setFilterProjectId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [isSpecificationModalOpen, setIsSpecificationModalOpen] = useState(false);
  const [editingSpecification, setEditingSpecification] =
    useState<Specification | null>(null);
  const [selectedSpecification, setSelectedSpecification] =
    useState<Specification | null>(null);
  const [isSourceModalOpen, setIsSourceModalOpen] = useState(false);
  const [selectedSource, setSelectedSource] =
    useState<SpecificationSourceDetail | null>(null);
  const [isSourceDetailLoading, setIsSourceDetailLoading] = useState(false);

  const [specificationForm, setSpecificationForm] =
    useState<SpecificationCreatePayload>(initialSpecificationForm);
  const [sourceForm, setSourceForm] = useState(initialSourceForm);

  const [isSavingSpecification, setIsSavingSpecification] = useState(false);
  const [isSavingSource, setIsSavingSource] = useState(false);
  const [savingRecordId, setSavingRecordId] = useState<string | null>(null);
  const [deletingSpecificationId, setDeletingSpecificationId] = useState<
    string | null
  >(null);
  const [deletingSourceId, setDeletingSourceId] = useState<string | null>(null);
  const [reparsingSourceId, setReparsingSourceId] = useState<string | null>(null);
  const [importingSourceId, setImportingSourceId] = useState<string | null>(null);

  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: project.id,
        label: `${project.name} - ${project.team_name}`,
      })),
    [projects]
  );

  const loadData = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setErrorMessage("");
      const [projectsData, specificationsData, sourcesData] = await Promise.all([
        getProjects(),
        getSpecifications(filterProjectId || undefined),
        getSpecificationSources(filterProjectId || undefined),
      ]);
      setProjects(projectsData);
      setSpecifications(specificationsData);
      setSources(sourcesData);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load specifications."));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [filterProjectId]);

  const openSpecificationCreateModal = (): void => {
    const defaultProject =
      filterProjectId || (projects.length === 1 ? projects[0].id : "");
    setEditingSpecification(null);
    setSpecificationForm({ ...initialSpecificationForm, project: defaultProject });
    setIsSpecificationModalOpen(true);
  };

  const openSpecificationEditModal = (specification: Specification): void => {
    setEditingSpecification(specification);
    setSpecificationForm({
      project: specification.project,
      title: specification.title,
      content: specification.content,
      source_type: specification.source_type,
      jira_issue_key: specification.jira_issue_key ?? "",
      source_url: specification.source_url ?? "",
      version: specification.version,
    });
    setIsSpecificationModalOpen(true);
  };

  const openSourceModal = (): void => {
    const defaultProject =
      filterProjectId || (projects.length === 1 ? projects[0].id : "");
    setSourceForm({ ...initialSourceForm, project: defaultProject });
    setIsSourceModalOpen(true);
  };

  const loadSourceDetail = async (sourceId: string): Promise<void> => {
    try {
      setIsSourceDetailLoading(true);
      setErrorMessage("");
      setSelectedSource(await getSpecificationSource(sourceId));
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load import details."));
    } finally {
      setIsSourceDetailLoading(false);
    }
  };

  const handleSpecificationSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();
    try {
      setIsSavingSpecification(true);
      setErrorMessage("");
      setSuccessMessage("");
      const payload = {
        project: specificationForm.project,
        title: specificationForm.title.trim(),
        content: specificationForm.content.trim(),
        source_type: specificationForm.source_type ?? "manual",
        jira_issue_key: specificationForm.jira_issue_key?.trim() || null,
        source_url: specificationForm.source_url?.trim() || null,
        version: specificationForm.version?.trim() || "1.0",
      };
      if (editingSpecification) {
        await updateSpecification(editingSpecification.id, payload as SpecificationUpdatePayload);
        setSuccessMessage("Specification updated successfully.");
      } else {
        await createSpecification(payload as SpecificationCreatePayload);
        setSuccessMessage("Specification created successfully.");
      }
      setIsSpecificationModalOpen(false);
      setEditingSpecification(null);
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save specification."));
    } finally {
      setIsSavingSpecification(false);
    }
  };

  const handleSourceSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();
    try {
      setIsSavingSource(true);
      setErrorMessage("");
      setSuccessMessage("");
      const created = await createSpecificationSource({
        project: sourceForm.project,
        name: sourceForm.name.trim() || undefined,
        source_type: sourceForm.source_type,
        file: sourceForm.file,
        raw_text: sourceForm.raw_text,
        source_url: sourceForm.source_url.trim() || null,
        jira_issue_key: sourceForm.jira_issue_key.trim() || null,
        auto_parse: true,
      } as SpecificationSourceCreatePayload);
      setSelectedSource(created);
      setIsSourceModalOpen(false);
      setSuccessMessage("Specification import created successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to create specification import."));
    } finally {
      setIsSavingSource(false);
    }
  };

  const updateSelectedRecord = (
    recordId: string,
    updater: (record: SpecificationSourceRecord) => SpecificationSourceRecord
  ): void => {
    setSelectedSource((previous) =>
      previous
        ? {
            ...previous,
            records: previous.records.map((record) =>
              record.id === recordId ? updater(record) : record
            ),
          }
        : previous
    );
  };

  const refreshSelectedSource = async (sourceId: string): Promise<void> => {
    setSelectedSource(await getSpecificationSource(sourceId));
  };

  const handleSaveRecord = async (recordId: string): Promise<void> => {
    if (!selectedSource) return;
    const record = selectedSource.records.find((item) => item.id === recordId);
    if (!record) return;
    try {
      setSavingRecordId(recordId);
      const updated = await updateSpecificationSourceRecord(selectedSource.id, recordId, {
        title: record.title,
        content: record.content,
        is_selected: record.is_selected,
        external_reference: record.external_reference,
        section_label: record.section_label,
      });
      updateSelectedRecord(recordId, () => updated);
      setSuccessMessage("Source record updated successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update source record."));
    } finally {
      setSavingRecordId(null);
    }
  };

  const handleDeleteSpecification = async (
    specification: Specification
  ): Promise<void> => {
    if (!globalThis.confirm(`Delete ${specification.title}?`)) return;
    try {
      setDeletingSpecificationId(specification.id);
      await deleteSpecification(specification.id);
      setSuccessMessage("Specification deleted successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete specification."));
    } finally {
      setDeletingSpecificationId(null);
    }
  };

  const handleDeleteSource = async (source: SpecificationSource): Promise<void> => {
    if (!globalThis.confirm(`Delete the import source ${source.name}?`)) return;
    try {
      setDeletingSourceId(source.id);
      await deleteSpecificationSource(source.id);
      if (selectedSource?.id === source.id) setSelectedSource(null);
      setSuccessMessage("Specification import deleted successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete specification import."));
    } finally {
      setDeletingSourceId(null);
    }
  };

  const handleReparseSource = async (sourceId: string): Promise<void> => {
    try {
      setReparsingSourceId(sourceId);
      setSelectedSource(await parseSpecificationSource(sourceId));
      setSuccessMessage("Specification import parsed successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to parse specification import."));
    } finally {
      setReparsingSourceId(null);
    }
  };

  const handleImportSource = async (sourceId: string): Promise<void> => {
    try {
      setImportingSourceId(sourceId);
      const response = await importSpecificationSource(sourceId);
      setSuccessMessage(
        response.imported_count > 0
          ? `${response.imported_count} specification(s) imported successfully.`
          : "No selected records were available to import."
      );
      await loadData();
      await refreshSelectedSource(sourceId);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to import selected records."));
    } finally {
      setImportingSourceId(null);
    }
  };

  const getSourcePreview = (record: SpecificationSourceRecord) => ({
    module: record.section_label || selectedSource?.project_name || "-",
    requirementId:
      record.external_reference || selectedSource?.jira_issue_key || "-",
    summary: record.title,
    description: record.content,
    section: record.section_label || selectedSource?.team_name || "-",
  });

  return (
    <div className="min-h-screen space-y-8 bg-gray-50">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Specifications</h1>
          <p className="mt-1 max-w-3xl text-sm text-gray-600">
            Import CSV, XLSX, PDF, DOCX, text, Jira, or URL context, review the
            parsed records, and turn them into normalized specifications for RAG.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          {projects.length > 0 ? (
            <Button variant="secondary" onClick={openSourceModal}>
              New Import
            </Button>
          ) : null}
          {projects.length > 0 ? (
            <Button onClick={openSpecificationCreateModal}>New Specification</Button>
          ) : null}
        </div>
      </div>

      {successMessage ? (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {successMessage}
        </div>
      ) : null}

      {errorMessage ? (
        <ErrorMessage message={errorMessage} onDismiss={() => setErrorMessage("")} />
      ) : null}

      <div className="max-w-md">
        <FormSelect
          id="specifications-filter-project"
          label="Filter by project"
          value={filterProjectId}
          onChange={(event) => setFilterProjectId(event.target.value)}
          options={projectOptions}
          placeholder="All projects"
        />
      </div>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Import Sources</h2>
          <p className="mt-1 text-sm text-gray-600">
            Keep your BIAT-IT source files close to the product context instead of
            importing them blindly into tests.
          </p>
        </div>

        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
          {isLoading ? (
            <div className="flex min-h-[180px] items-center justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : sources.length === 0 ? (
            <div className="p-6 text-sm text-gray-500">
              No import sources found for this filter.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Import
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Project
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Type
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Status
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Records
                  </th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="font-medium">{source.name}</div>
                      <div className="mt-1 text-xs text-gray-500">
                        {source.file_name ?? source.uploaded_by_name ?? "-"}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <div>{source.project_name}</div>
                      <div className="mt-1 text-xs text-gray-500">{source.team_name}</div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {labelize(source.source_type)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <div>{labelize(source.parser_status)}</div>
                      {source.parser_error ? (
                        <div className="mt-1 text-xs text-red-600">{source.parser_error}</div>
                      ) : null}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <div>{source.record_count} parsed</div>
                      <div className="mt-1 text-xs text-gray-500">
                        {source.selected_record_count} selected / {source.imported_record_count} imported
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right text-sm">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="md"
                          onClick={() => void loadSourceDetail(source.id)}
                        >
                          Review
                        </Button>
                        {source.can_manage ? (
                          <>
                            <Button
                              variant="secondary"
                              size="md"
                              onClick={() => void handleReparseSource(source.id)}
                              isLoading={reparsingSourceId === source.id}
                              loadingText="Parsing..."
                            >
                              Reparse
                            </Button>
                            <Button
                              size="md"
                              onClick={() => void handleImportSource(source.id)}
                              isLoading={importingSourceId === source.id}
                              loadingText="Importing..."
                              disabled={source.selected_record_count === 0}
                            >
                              Import
                            </Button>
                            <Button
                              variant="danger"
                              size="md"
                              onClick={() => void handleDeleteSource(source)}
                              isLoading={deletingSourceId === source.id}
                              loadingText="Deleting..."
                            >
                              Delete
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Normalized Specifications</h2>
          <p className="mt-1 text-sm text-gray-600">
            These are the clean records used by chunking, retrieval, and the next AI
            testing layers.
          </p>
        </div>

        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
          {isLoading ? (
            <div className="flex min-h-[220px] items-center justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : specifications.length === 0 ? (
            <div className="p-6 text-sm text-gray-500">No specifications found.</div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Specification
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Project
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Source
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Version
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Chunks
                  </th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {specifications.map((specification) => (
                  <tr key={specification.id}>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="font-medium">{specification.title}</div>
                      <div className="mt-1 text-xs text-gray-500">
                        {specification.content.slice(0, 120)}
                        {specification.content.length > 120 ? "..." : ""}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <div>{specification.project_name}</div>
                      <div className="mt-1 text-xs text-gray-500">{specification.team_name}</div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <div>{labelize(specification.source_type)}</div>
                      <div className="mt-1 text-xs text-gray-500">
                        {specification.source_name ?? specification.external_reference ?? "-"}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{specification.version}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{specification.chunk_count}</td>
                    <td className="px-6 py-4 text-right text-sm">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="md"
                          onClick={() => setSelectedSpecification(specification)}
                        >
                          Details
                        </Button>
                        {specification.can_manage ? (
                          <>
                            <Button
                              variant="secondary"
                              size="md"
                              onClick={() => openSpecificationEditModal(specification)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="danger"
                              size="md"
                              onClick={() => void handleDeleteSpecification(specification)}
                              isLoading={deletingSpecificationId === specification.id}
                              loadingText="Deleting..."
                            >
                              Delete
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <Modal isOpen={isSourceModalOpen} onClose={() => setIsSourceModalOpen(false)} title="Create Specification Import" size="xl">
        <form onSubmit={handleSourceSubmit} className="space-y-4">
          <FormSelect
            id="source-project"
            label="Project"
            value={sourceForm.project}
            onChange={(event) => setSourceForm((previous) => ({ ...previous, project: event.target.value }))}
            options={projectOptions}
            placeholder="Select project"
            required
          />
          <div className="grid gap-4 md:grid-cols-2">
            <FormInput
              id="source-name"
              label="Import name"
              type="text"
              value={sourceForm.name}
              onChange={(event) => setSourceForm((previous) => ({ ...previous, name: event.target.value }))}
              helperText="Optional. The file name or source reference can be used instead."
            />
            <FormSelect
              id="source-type"
              label="Source type"
              value={sourceForm.source_type}
              onChange={(event) =>
                setSourceForm((previous) => ({
                  ...previous,
                  source_type: event.target.value as SpecificationSourceType,
                  file: null,
                }))
              }
              options={IMPORT_SOURCE_OPTIONS}
              required
            />
          </div>
          {isFileSource(sourceForm.source_type) ? (
            <div>
              <label htmlFor="source-file" className="mb-1.5 block text-sm font-medium text-gray-700">
                Source file
              </label>
              <input
                id="source-file"
                type="file"
                onChange={(event) =>
                  setSourceForm((previous) => ({
                    ...previous,
                    file: event.target.files?.[0] ?? null,
                  }))
                }
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-gray-900"
                required
              />
            </div>
          ) : null}
          {sourceForm.source_type === "jira_issue" ? (
            <FormInput
              id="source-jira-key"
              label="Jira issue key"
              type="text"
              value={sourceForm.jira_issue_key}
              onChange={(event) => setSourceForm((previous) => ({ ...previous, jira_issue_key: event.target.value }))}
              required
            />
          ) : null}
          {sourceForm.source_type === "url" ? (
            <FormInput
              id="source-url"
              label="Source URL"
              type="url"
              value={sourceForm.source_url}
              onChange={(event) => setSourceForm((previous) => ({ ...previous, source_url: event.target.value }))}
              required
            />
          ) : null}
          {hasTextArea(sourceForm.source_type) ? (
            <div>
              <label htmlFor="source-text" className="mb-1.5 block text-sm font-medium text-gray-700">
                Source content
              </label>
              <textarea
                id="source-text"
                value={sourceForm.raw_text}
                onChange={(event) => setSourceForm((previous) => ({ ...previous, raw_text: event.target.value }))}
                rows={10}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-gray-900"
                required={sourceForm.source_type === "plain_text"}
              />
            </div>
          ) : null}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setIsSourceModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSavingSource} loadingText="Creating...">
              Create Import
            </Button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={isSpecificationModalOpen} onClose={() => setIsSpecificationModalOpen(false)} title={editingSpecification ? "Edit Specification" : "Create Specification"} size="xl">
        <form onSubmit={handleSpecificationSubmit} className="space-y-4">
          <FormSelect
            id="specification-project"
            label="Project"
            value={specificationForm.project}
            onChange={(event) => setSpecificationForm((previous) => ({ ...previous, project: event.target.value }))}
            options={projectOptions}
            placeholder="Select project"
            required
          />
          <div className="grid gap-4 md:grid-cols-2">
            <FormInput id="specification-title" label="Title" type="text" value={specificationForm.title} onChange={(event) => setSpecificationForm((previous) => ({ ...previous, title: event.target.value }))} required />
            <FormInput id="specification-version" label="Version" type="text" value={specificationForm.version ?? "1.0"} onChange={(event) => setSpecificationForm((previous) => ({ ...previous, version: event.target.value }))} required />
          </div>
          <FormSelect
            id="specification-source-type"
            label="Source type"
            value={specificationForm.source_type ?? "manual"}
            onChange={(event) => setSpecificationForm((previous) => ({ ...previous, source_type: event.target.value as SpecificationSourceType }))}
            options={SPEC_SOURCE_OPTIONS}
            required
          />
          <div className="grid gap-4 md:grid-cols-2">
            <FormInput id="specification-jira-key" label="Jira issue key" type="text" value={specificationForm.jira_issue_key ?? ""} onChange={(event) => setSpecificationForm((previous) => ({ ...previous, jira_issue_key: event.target.value }))} />
            <FormInput id="specification-source-url" label="Source URL" type="url" value={specificationForm.source_url ?? ""} onChange={(event) => setSpecificationForm((previous) => ({ ...previous, source_url: event.target.value }))} />
          </div>
          <div>
            <label htmlFor="specification-content" className="mb-1.5 block text-sm font-medium text-gray-700">
              Content
            </label>
            <textarea
              id="specification-content"
              value={specificationForm.content}
              onChange={(event) => setSpecificationForm((previous) => ({ ...previous, content: event.target.value }))}
              rows={12}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-gray-900"
              required
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setIsSpecificationModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSavingSpecification} loadingText="Saving...">
              {editingSpecification ? "Update" : "Create"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={Boolean(selectedSource) || isSourceDetailLoading}
        onClose={() => setSelectedSource(null)}
        title={selectedSource ? `${selectedSource.name} Import Review` : "Import Review"}
        size="xl"
      >
        {isSourceDetailLoading ? (
          <div className="flex min-h-[220px] items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : selectedSource ? (
          <div className="space-y-6">
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
              <div className="grid gap-4 md:grid-cols-4">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Type</p>
                  <p className="mt-1 text-sm text-gray-700">{labelize(selectedSource.source_type)}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Status</p>
                  <p className="mt-1 text-sm text-gray-700">{labelize(selectedSource.parser_status)}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Project</p>
                  <p className="mt-1 text-sm text-gray-700">{selectedSource.project_name}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Records</p>
                  <p className="mt-1 text-sm text-gray-700">
                    {selectedSource.record_count} parsed / {selectedSource.selected_record_count} selected
                  </p>
                </div>
              </div>
              {selectedSource.can_manage ? (
                <div className="mt-4 flex flex-wrap justify-end gap-3">
                  <Button
                    variant="secondary"
                    onClick={() => void handleReparseSource(selectedSource.id)}
                    isLoading={reparsingSourceId === selectedSource.id}
                    loadingText="Parsing..."
                  >
                    Reparse
                  </Button>
                  <Button
                    onClick={() => void handleImportSource(selectedSource.id)}
                    isLoading={importingSourceId === selectedSource.id}
                    loadingText="Importing..."
                    disabled={selectedSource.records.filter((record) => record.is_selected).length === 0}
                  >
                    Import Selected
                  </Button>
                </div>
              ) : null}
            </div>

            {selectedSource.records.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-6 text-sm text-gray-500">
                No parsed records are available for this source yet.
              </div>
            ) : (
              selectedSource.records.map((record) => {
                const preview = getSourcePreview(record);
                return (
                  <div key={record.id} className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                          Record {record.record_index + 1}
                        </p>
                        <p className="mt-1 text-sm text-gray-700">
                          {labelize(record.import_status)}
                          {record.row_number ? ` - row ${record.row_number}` : ""}
                        </p>
                      </div>
                      <label className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={record.is_selected}
                          onChange={(event) =>
                            updateSelectedRecord(record.id, (current) => ({
                              ...current,
                              is_selected: event.target.checked,
                            }))
                          }
                          className="h-4 w-4 rounded border-gray-300"
                          disabled={!selectedSource.can_manage}
                        />
                        Select for import
                      </label>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <FormInput
                        id={`record-title-${record.id}`}
                        label="Title"
                        type="text"
                        value={record.title}
                        onChange={(event) =>
                          updateSelectedRecord(record.id, (current) => ({
                            ...current,
                            title: event.target.value,
                          }))
                        }
                        disabled={!selectedSource.can_manage}
                      />
                      <FormInput
                        id={`record-reference-${record.id}`}
                        label="External reference"
                        type="text"
                        value={record.external_reference}
                        onChange={(event) =>
                          updateSelectedRecord(record.id, (current) => ({
                            ...current,
                            external_reference: event.target.value,
                          }))
                        }
                        disabled={!selectedSource.can_manage}
                      />
                    </div>

                    <div className="mt-4">
                      <FormInput
                        id={`record-section-${record.id}`}
                        label="Section label"
                        type="text"
                        value={record.section_label}
                        onChange={(event) =>
                          updateSelectedRecord(record.id, (current) => ({
                            ...current,
                            section_label: event.target.value,
                          }))
                        }
                        disabled={!selectedSource.can_manage}
                      />
                    </div>

                    <div className="mt-4">
                      <label htmlFor={`record-content-${record.id}`} className="mb-1.5 block text-sm font-medium text-gray-700">
                        Content
                      </label>
                      <textarea
                        id={`record-content-${record.id}`}
                        value={record.content}
                        onChange={(event) =>
                          updateSelectedRecord(record.id, (current) => ({
                            ...current,
                            content: event.target.value,
                          }))
                        }
                        rows={6}
                        className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-gray-900"
                        disabled={!selectedSource.can_manage}
                      />
                    </div>

                    <div className="mt-4 rounded-2xl border border-gray-200 bg-white p-4">
                      <h3 className="text-sm font-semibold text-gray-900">qTest-style preview</h3>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Module</p>
                          <p className="mt-1 text-sm text-gray-700">{preview.module}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Requirement ID</p>
                          <p className="mt-1 text-sm text-gray-700">{preview.requirementId}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Summary</p>
                          <p className="mt-1 text-sm text-gray-700">{preview.summary}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Section</p>
                          <p className="mt-1 text-sm text-gray-700">{preview.section}</p>
                        </div>
                      </div>
                      <p className="mt-3 whitespace-pre-wrap text-sm text-gray-700">{preview.description}</p>
                    </div>

                    {selectedSource.can_manage ? (
                      <div className="mt-4 flex justify-end">
                        <Button
                          onClick={() => void handleSaveRecord(record.id)}
                          isLoading={savingRecordId === record.id}
                          loadingText="Saving..."
                        >
                          Save Record
                        </Button>
                      </div>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
        ) : null}
      </Modal>

      <Modal
        isOpen={Boolean(selectedSpecification)}
        onClose={() => setSelectedSpecification(null)}
        title={selectedSpecification ? `${selectedSpecification.title} Details` : "Specification Details"}
        size="xl"
      >
        {selectedSpecification ? (
          <div className="space-y-6">
            <div className="rounded-2xl border border-gray-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-gray-900">qTest-style preview</h3>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Module</p>
                  <p className="mt-1 text-sm text-gray-700">{selectedSpecification.qtest_preview.module}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Requirement ID</p>
                  <p className="mt-1 text-sm text-gray-700">{selectedSpecification.qtest_preview.requirement_id || "-"}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Summary</p>
                  <p className="mt-1 text-sm text-gray-700">{selectedSpecification.qtest_preview.summary}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Section</p>
                  <p className="mt-1 text-sm text-gray-700">{selectedSpecification.qtest_preview.section}</p>
                </div>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm text-gray-700">
                {selectedSpecification.qtest_preview.description}
              </p>
            </div>

            <div className="space-y-4">
              {selectedSpecification.chunks.length ? (
                selectedSpecification.chunks.map((chunk) => (
                  <div key={chunk.id} className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                      <span>Chunk {chunk.chunk_index + 1}</span>
                      <span className="rounded-full bg-white px-2 py-1 text-[11px] text-gray-600">
                        {labelize(chunk.chunk_type)}
                      </span>
                      {chunk.component_tag ? (
                        <span className="rounded-full bg-white px-2 py-1 text-[11px] text-gray-600">
                          {chunk.component_tag}
                        </span>
                      ) : null}
                      <span className="rounded-full bg-white px-2 py-1 text-[11px] text-gray-600">
                        {chunk.token_count} tokens
                      </span>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm text-gray-700">{chunk.content}</p>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-6 text-sm text-gray-500">
                  No chunks found for this specification.
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
