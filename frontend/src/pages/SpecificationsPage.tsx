/** Specification import and review workspace redesigned around branded data-heavy surfaces. */
import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  SpecificationsDetailPanel,
  type SpecificationDetailTab,
} from "../components/specifications/SpecificationsDetailPanel";
import {
  SpecificationsTreePanel,
  type SpecificationTreeSource,
} from "../components/specifications/SpecificationsTreePanel";
import {
  getSourceDisplayName,
  getSpecificationGroupLabel,
  getSpecificationGroupSubtitle,
  getStatusVariant,
  labelize,
} from "../components/specifications/presentation";
import { Badge, EmptyState } from "../components/ui";
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
const isFileSource = (value: SpecificationSourceType) =>
  value === "csv" || value === "xlsx" || value === "pdf" || value === "docx";
const hasTextArea = (value: SpecificationSourceType) =>
  value === "manual" ||
  value === "plain_text" ||
  value === "jira_issue" ||
  value === "url";

function SourceImportIcon() {
  return (
    <svg className="h-10 w-10" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <rect x="8" y="8" width="32" height="24" rx="6" className="stroke-primary" strokeWidth="2.5" />
      <path d="M16 38h16" className="stroke-primary-light" strokeWidth="2.5" strokeLinecap="round" />
      <path d="m24 17 6 6m0 0-6 6m6-6H18" className="stroke-warm" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function buildSpecificationTreeSources(
  sources: SpecificationSource[],
  specifications: Specification[]
): SpecificationTreeSource[] {
  const sourceNodes = new Map<string, SpecificationTreeSource>();
  const groupsBySourceKey = new Map<
    string,
    Map<string, SpecificationTreeSource["groups"][number]>
  >();

  sources.forEach((source) => {
    sourceNodes.set(`source:${source.id}`, {
      key: `source:${source.id}`,
      sourceId: source.id,
      label: getSourceDisplayName(source) ?? "Imported source",
      subtitle: `${source.project_name} / ${labelize(source.source_type)}`,
      statusLabel: labelize(source.parser_status),
      statusVariant: getStatusVariant(source.parser_status),
      source,
      groups: [],
      specificationCount: 0,
    });
  });

  specifications.forEach((specification) => {
    const sourceKey = specification.source_id
      ? `source:${specification.source_id}`
      : "source:standalone";

    if (!sourceNodes.has(sourceKey)) {
      sourceNodes.set(sourceKey, {
        key: sourceKey,
        sourceId: specification.source_id,
        label:
          specification.source_id && specification.source_name
            ? specification.source_name
            : "Standalone specifications",
        subtitle: specification.source_id
          ? `${specification.project_name} / ${labelize(specification.source_type)}`
          : "Created directly in the platform",
        statusLabel: specification.source_id ? "imported" : "manual",
        statusVariant: "verified",
        source: null,
        groups: [],
        specificationCount: 0,
      });
    }

    const sourceNode = sourceNodes.get(sourceKey);
    if (!sourceNode) {
      return;
    }

    sourceNode.specificationCount += 1;

    const groupLabel = getSpecificationGroupLabel(specification);
    const groupMap = groupsBySourceKey.get(sourceKey) ?? new Map();
    let group = groupMap.get(groupLabel);

    if (!group) {
      group = {
        key: `${sourceKey}:group:${encodeURIComponent(groupLabel.toLowerCase())}`,
        sourceKey,
        sourceId: sourceNode.sourceId,
        label: groupLabel,
        subtitle: getSpecificationGroupSubtitle(specification),
        specifications: [],
      };
      groupMap.set(groupLabel, group);
      sourceNode.groups.push(group);
      groupsBySourceKey.set(sourceKey, groupMap);
    }

    group.specifications.push(specification);
  });

  return [...sourceNodes.values()]
    .map((source) => ({
      ...source,
      groups: source.groups
        .map((group) => ({
          ...group,
          specifications: [...group.specifications].sort((left, right) =>
            left.title.localeCompare(right.title)
          ),
        }))
        .sort((left, right) => left.label.localeCompare(right.label)),
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

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
  const [selectedSourceKey, setSelectedSourceKey] = useState("");
  const [selectedGroupKey, setSelectedGroupKey] = useState("");
  const [selectedSpecificationId, setSelectedSpecificationId] = useState("");
  const [selectedSpecificationIds, setSelectedSpecificationIds] = useState<
    string[]
  >([]);
  const [selectedGroupPage, setSelectedGroupPage] = useState(1);
  const [activeDetailTab, setActiveDetailTab] =
    useState<SpecificationDetailTab>("overview");

  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: project.id,
        label: `${project.name} - ${project.team_name}`,
      })),
    [projects]
  );

  const specificationTreeSources = useMemo(
    () => buildSpecificationTreeSources(sources, specifications),
    [sources, specifications]
  );
  const selectedTreeSource =
    specificationTreeSources.find((source) => source.key === selectedSourceKey) ??
    specificationTreeSources[0] ??
    null;
  const selectedTreeGroup =
    selectedTreeSource?.groups.find((group) => group.key === selectedGroupKey) ??
    null;
  const selectedTreeSpecification =
    selectedTreeGroup?.specifications.find(
      (specification) => specification.id === selectedSpecificationId
    ) ?? null;

  const loadData = useCallback(async (): Promise<void> => {
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
  }, [filterProjectId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (specificationTreeSources.length === 0) {
      setSelectedSourceKey("");
      setSelectedGroupKey("");
      setSelectedSpecificationId("");
      return;
    }

    const sourceStillExists = specificationTreeSources.some(
      (source) => source.key === selectedSourceKey
    );

    if (!sourceStillExists) {
      const firstSource = specificationTreeSources[0];
      setSelectedSourceKey(firstSource.key);
      setSelectedGroupKey(firstSource.groups[0]?.key ?? "");
      setSelectedSpecificationId("");
      return;
    }

    const currentSource = specificationTreeSources.find(
      (source) => source.key === selectedSourceKey
    );

    if (!currentSource) {
      return;
    }

    if (
      selectedGroupKey &&
      !currentSource.groups.some((group) => group.key === selectedGroupKey)
    ) {
      setSelectedGroupKey(currentSource.groups[0]?.key ?? "");
      setSelectedSpecificationId("");
      return;
    }

    if (
      selectedSpecificationId &&
      !currentSource.groups.some((group) =>
        group.specifications.some(
          (specification) => specification.id === selectedSpecificationId
        )
      )
    ) {
      setSelectedSpecificationId("");
    }
  }, [
    specificationTreeSources,
    selectedSourceKey,
    selectedGroupKey,
    selectedSpecificationId,
  ]);

  useEffect(() => {
    setSelectedGroupPage(1);
  }, [selectedGroupKey]);

  useEffect(() => {
    setActiveDetailTab("overview");
  }, [selectedSpecificationId]);

  useEffect(() => {
    const specificationIds = new Set(specifications.map((specification) => specification.id));
    setSelectedSpecificationIds((previous) =>
      previous.filter((specificationId) => specificationIds.has(specificationId))
    );
  }, [specifications]);

  const handleSelectSource = (sourceKey: string): void => {
    setSelectedSourceKey(sourceKey);
    setSelectedGroupKey("");
    setSelectedSpecificationId("");
  };

  const handleSelectGroup = (sourceKey: string, groupKey: string): void => {
    setSelectedSourceKey(sourceKey);
    setSelectedGroupKey(groupKey);
    setSelectedSpecificationId("");
  };

  const handleSelectSpecification = (
    sourceKey: string,
    groupKey: string,
    specificationId: string
  ): void => {
    setSelectedSourceKey(sourceKey);
    setSelectedGroupKey(groupKey);
    setSelectedSpecificationId(specificationId);
  };

  const handleToggleSpecificationSelection = (specificationId: string): void => {
    setSelectedSpecificationIds((previous) =>
      previous.includes(specificationId)
        ? previous.filter((id) => id !== specificationId)
        : [...previous, specificationId]
    );
  };

  const handleTogglePageSelection = (
    specificationIds: string[],
    isSelected: boolean
  ): void => {
    setSelectedSpecificationIds((previous) => {
      const next = new Set(previous);
      specificationIds.forEach((specificationId) => {
        if (isSelected) {
          next.add(specificationId);
        } else {
          next.delete(specificationId);
        }
      });
      return [...next];
    });
  };

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

  const openSourceModalForType = (sourceType: SpecificationSourceType): void => {
    const defaultProject =
      filterProjectId || (projects.length === 1 ? projects[0].id : "");
    setSourceForm({
      ...initialSourceForm,
      project: defaultProject,
      source_type: sourceType,
    });
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
      setSelectedSpecificationId((previous) =>
        previous === specification.id ? "" : previous
      );
      setSelectedSpecificationIds((previous) =>
        previous.filter((specificationId) => specificationId !== specification.id)
      );
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
      if (selectedSourceKey === `source:${source.id}`) {
        setSelectedSourceKey("");
        setSelectedGroupKey("");
        setSelectedSpecificationId("");
      }
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

  const getStructuredFields = (metadata: Record<string, unknown> | undefined) => {
    const structuredFields = metadata?.structured_fields;
    if (!structuredFields || typeof structuredFields !== "object" || Array.isArray(structuredFields)) {
      return {} as Record<string, string>;
    }

    return Object.fromEntries(
      Object.entries(structuredFields).filter(([, value]) => typeof value === "string" && value.trim()),
    ) as Record<string, string>;
  };

  const buildStructuredDescription = (fields: Record<string, string>, fallback: string) => {
    const lines: string[] = [];

    if (fields.description) lines.push(`Description: ${fields.description}`);
    if (fields.actor) lines.push(`Acteur: ${fields.actor}`);
    if (fields.preconditions) lines.push(`Precondition: ${fields.preconditions}`);
    if (fields.steps) lines.push(`Steps: ${fields.steps}`);
    if (fields.acceptance_criteria) {
      lines.push(`Criteres d'acceptation: ${fields.acceptance_criteria}`);
    }
    if (fields.priority) lines.push(`Priorite: ${fields.priority}`);
    if (fields.version) lines.push(`Version: ${fields.version}`);
    if (fields.url) lines.push(`URL de reference: ${fields.url}`);

    return lines.length ? lines.join("\n") : fallback;
  };

  const getSourcePreview = (record: SpecificationSourceRecord) => {
    const structuredFields = getStructuredFields(record.record_metadata);

    return {
      module:
        structuredFields.module ||
        record.section_label ||
        selectedSource?.project_name ||
        "-",
      requirementId:
        structuredFields.reference ||
        record.external_reference ||
        selectedSource?.jira_issue_key ||
        "-",
      summary: structuredFields.title || record.title,
      description: buildStructuredDescription(structuredFields, record.content),
      section:
        structuredFields.section ||
        record.section_label ||
        selectedSource?.team_name ||
        "-",
      preconditions: structuredFields.preconditions || "",
      expectedResult: structuredFields.expected_result || "",
    };
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Badge variant="tag">Context workspace</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text">Specifications</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Import CSV, XLSX, PDF, DOCX, text, Jira, or URL context, review the
            parsed records, and turn them into structured requirements for traceability and test design.
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
        <div className="rounded-2xl border border-status-verified-text/15 bg-status-verified-bg px-4 py-3 text-sm text-status-verified-text shadow-sm">
          {successMessage}
        </div>
      ) : null}

      {errorMessage ? (
        <ErrorMessage message={errorMessage} onDismiss={() => setErrorMessage("")} />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div>
          <FormSelect
            id="specifications-filter-project"
            label="Filter by project"
            value={filterProjectId}
            onChange={(event) => setFilterProjectId(event.target.value)}
            options={projectOptions}
            placeholder="All projects"
          />
        </div>
        <div className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Progressive disclosure
          </p>
          <p className="mt-2 text-sm leading-6 text-muted">
            The workspace now keeps heavy imported content hidden until you drill from source to grouped requirements to a single specification. Bulk row selection stays available in the list view, and detailed traceability or processing details only appear on demand.
          </p>
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-text">
            Specifications workspace
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Browse source context on the left, focus a grouped bucket in the middle, and inspect specification details only when needed.
          </p>
        </div>

        {isLoading ? (
          <div className="flex min-h-[280px] items-center justify-center rounded-[28px] border border-border bg-surface shadow-panel">
            <LoadingSpinner size="lg" />
          </div>
        ) : specificationTreeSources.length === 0 ? (
          <EmptyState
            icon={<SourceImportIcon />}
            title="Build your specifications workspace"
            description="Start with manual input for quick requirement capture or import a spreadsheet to structure source material before review, traceability, and test design."
            primaryAction={
              projects.length > 0 ? (
                <Button onClick={openSourceModal}>New Import</Button>
              ) : undefined
            }
            secondaryAction={
              projects.length > 0 ? (
                <Button
                  variant="secondary"
                  onClick={() => openSourceModalForType("xlsx")}
                >
                  Import CSV / XLSX
                </Button>
              ) : undefined
            }
          >
            {projects.length > 0 ? (
              <div className="flex justify-center">
                <Button variant="secondary" onClick={openSpecificationCreateModal}>
                  New Specification
                </Button>
              </div>
            ) : null}
          </EmptyState>
        ) : (
          <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
            <SpecificationsTreePanel
              sources={specificationTreeSources}
              selectedSourceKey={selectedSourceKey}
              selectedGroupKey={selectedGroupKey}
              selectedSpecificationId={selectedSpecificationId}
              onSelectSource={handleSelectSource}
              onSelectGroup={handleSelectGroup}
              onSelectSpecification={handleSelectSpecification}
            />

            <div className="min-w-0">
              <SpecificationsDetailPanel
                selectedSource={selectedTreeSource}
                selectedGroup={selectedTreeGroup}
                selectedSpecification={selectedTreeSpecification}
                selectedSpecificationIds={selectedSpecificationIds}
                selectedGroupPage={selectedGroupPage}
                pageSize={10}
                activeTab={activeDetailTab}
                deletingSpecificationId={deletingSpecificationId}
                deletingSourceId={deletingSourceId}
                reparsingSourceId={reparsingSourceId}
                importingSourceId={importingSourceId}
                onSelectGroup={handleSelectGroup}
                onSelectSpecification={handleSelectSpecification}
                onToggleSpecificationSelection={handleToggleSpecificationSelection}
                onTogglePageSelection={handleTogglePageSelection}
                onClearSelection={() => setSelectedSpecificationIds([])}
                onChangePage={setSelectedGroupPage}
                onChangeTab={setActiveDetailTab}
                onOpenSpecificationEdit={openSpecificationEditModal}
                onDeleteSpecification={(specification) =>
                  void handleDeleteSpecification(specification)
                }
                onOpenSourceReview={(sourceId) => void loadSourceDetail(sourceId)}
                onReparseSource={(sourceId) => void handleReparseSource(sourceId)}
                onImportSource={(sourceId) => void handleImportSource(sourceId)}
                onDeleteSource={(source) => void handleDeleteSource(source)}
              />
            </div>
          </div>
        )}
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
              <label
                htmlFor="source-file"
                className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
              >
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
                className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-text outline-none transition file:mr-3 file:rounded-xl file:border-0 file:bg-primary-light/10 file:px-3 file:py-2 file:font-medium file:text-primary hover:border-primary-light/50 focus-visible:ring-4 focus-visible:ring-primary-light/20"
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
              <label
                htmlFor="source-text"
                className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
              >
                Source content
              </label>
              <textarea
                id="source-text"
                value={sourceForm.raw_text}
                onChange={(event) => setSourceForm((previous) => ({ ...previous, raw_text: event.target.value }))}
                rows={10}
                className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
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
            <label
              htmlFor="specification-content"
              className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
            >
              Content
            </label>
            <textarea
              id="specification-content"
              value={specificationForm.content}
              onChange={(event) => setSpecificationForm((previous) => ({ ...previous, content: event.target.value }))}
              rows={12}
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
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
        actions={
          selectedSource?.can_manage ? (
            <Button
              variant="secondary"
              onClick={() => void handleReparseSource(selectedSource.id)}
              isLoading={reparsingSourceId === selectedSource.id}
              loadingText="Parsing..."
            >
              Reparse
            </Button>
          ) : undefined
        }
        footer={
          selectedSource ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted">
                {selectedSource.records.length} records /{" "}
                {
                  selectedSource.records.filter((record) => record.is_selected)
                    .length
                }{" "}
                selected
              </p>
              <div className="flex gap-3">
                <Button variant="secondary" onClick={() => setSelectedSource(null)}>
                  Close
                </Button>
                {selectedSource.can_manage ? (
                  <Button
                    onClick={() => void handleImportSource(selectedSource.id)}
                    isLoading={importingSourceId === selectedSource.id}
                    loadingText="Importing..."
                    disabled={
                      selectedSource.records.filter((record) => record.is_selected)
                        .length === 0
                    }
                  >
                    Import Selected
                  </Button>
                ) : null}
              </div>
            </div>
          ) : undefined
        }
      >
        {isSourceDetailLoading ? (
          <div className="flex min-h-[220px] items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : selectedSource ? (
          <div className="space-y-6">
            <div className="rounded-[28px] border border-border bg-bg p-5">
              <div className="grid gap-4 md:grid-cols-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Type</p>
                  <div className="mt-2">
                    <Badge variant="tag">{labelize(selectedSource.source_type)}</Badge>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Status</p>
                  <div className="mt-2">
                    <Badge variant={getStatusVariant(selectedSource.parser_status)}>
                      {labelize(selectedSource.parser_status)}
                    </Badge>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Project</p>
                  <p className="mt-2 text-sm font-medium text-text">{selectedSource.project_name}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Records</p>
                  <p className="mt-2 text-sm font-medium text-text">
                    {selectedSource.record_count} parsed / {selectedSource.selected_record_count} selected
                  </p>
                </div>
              </div>
            </div>

            {selectedSource.records.length === 0 ? (
              <div className="rounded-[28px] border border-dashed border-border bg-surface p-6 text-sm text-muted">
                No parsed records are available for this source yet.
              </div>
            ) : (
              selectedSource.records.map((record) => {
                const preview = getSourcePreview(record);
                return (
                  <div key={record.id} className="rounded-[28px] border border-border bg-bg p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                          Record {record.record_index + 1}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-text">
                          <Badge variant={getStatusVariant(record.import_status)}>
                            {labelize(record.import_status)}
                          </Badge>
                          {record.row_number ? ` - row ${record.row_number}` : ""}
                        </div>
                      </div>
                      <label className="flex items-center gap-2 text-sm text-text">
                        <input
                          type="checkbox"
                          checked={record.is_selected}
                          onChange={(event) =>
                            updateSelectedRecord(record.id, (current) => ({
                              ...current,
                              is_selected: event.target.checked,
                            }))
                          }
                          className="h-4 w-4 rounded border-border text-primary focus:ring-primary-light"
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
                      <label
                        htmlFor={`record-content-${record.id}`}
                        className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
                      >
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
                        className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
                        disabled={!selectedSource.can_manage}
                      />
                    </div>

                    <div className="mt-4 rounded-[28px] border border-border bg-surface p-5 shadow-sm">
                      <h3 className="text-sm font-semibold tracking-tight text-text">qTest-style preview</h3>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Module</p>
                          <p className="mt-1 text-sm text-text">{preview.module}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Requirement ID</p>
                          <p className="mt-1 text-sm text-text">{preview.requirementId}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Summary</p>
                          <p className="mt-1 text-sm text-text">{preview.summary}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Section</p>
                          <p className="mt-1 text-sm text-text">{preview.section}</p>
                        </div>
                      </div>
                      {preview.preconditions ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Preconditions</p>
                          <p className="mt-1 whitespace-pre-wrap text-sm text-text">{preview.preconditions}</p>
                        </div>
                      ) : null}
                      {preview.expectedResult ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Expected Result</p>
                          <p className="mt-1 whitespace-pre-wrap text-sm text-text">{preview.expectedResult}</p>
                        </div>
                      ) : null}
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-text">{preview.description}</p>
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
    </div>
  );
}
