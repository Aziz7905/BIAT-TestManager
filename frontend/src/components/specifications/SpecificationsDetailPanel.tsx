import { Button } from "../Button";
import { Badge, EmptyState } from "../ui";
import type { Specification, SpecificationSource } from "../../types/specs";
import type {
  SpecificationTreeGroup,
  SpecificationTreeSource,
} from "./SpecificationsTreePanel";
import {
  buildTraceabilityGroups,
  formatDate,
  getPriorityVariant,
  getSourceDisplayName,
  getSpecificationPresentation,
  labelize,
} from "./presentation";

export type SpecificationDetailTab =
  | "overview"
  | "normalized-content"
  | "test-design"
  | "traceability"
  | "rag";

interface SpecificationsDetailPanelProps {
  selectedSource: SpecificationTreeSource | null;
  selectedGroup: SpecificationTreeGroup | null;
  selectedSpecification: Specification | null;
  selectedSpecificationIds: string[];
  selectedGroupPage: number;
  pageSize: number;
  activeTab: SpecificationDetailTab;
  deletingSpecificationId: string | null;
  deletingSourceId: string | null;
  reparsingSourceId: string | null;
  importingSourceId: string | null;
  onSelectGroup: (sourceKey: string, groupKey: string) => void;
  onSelectSpecification: (
    sourceKey: string,
    groupKey: string,
    specificationId: string
  ) => void;
  onToggleSpecificationSelection: (specificationId: string) => void;
  onTogglePageSelection: (specificationIds: string[], isSelected: boolean) => void;
  onClearSelection: () => void;
  onChangePage: (page: number) => void;
  onChangeTab: (tab: SpecificationDetailTab) => void;
  onOpenSpecificationEdit: (specification: Specification) => void;
  onDeleteSpecification: (specification: Specification) => void;
  onOpenSourceReview: (sourceId: string) => void;
  onReparseSource: (sourceId: string) => void;
  onImportSource: (sourceId: string) => void;
  onDeleteSource: (source: SpecificationSource) => void;
}

function SpecificationWorkspaceIcon() {
  return (
    <svg className="h-10 w-10" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <rect
        x="7"
        y="8"
        width="14"
        height="32"
        rx="4"
        className="stroke-primary"
        strokeWidth="2.5"
      />
      <rect
        x="27"
        y="8"
        width="14"
        height="13"
        rx="4"
        className="stroke-primary-light"
        strokeWidth="2.5"
      />
      <rect
        x="27"
        y="27"
        width="14"
        height="13"
        rx="4"
        className="stroke-warm"
        strokeWidth="2.5"
      />
    </svg>
  );
}

function MetricCard({
  label,
  value,
  helper,
}: Readonly<{
  label: string;
  value: string | number;
  helper?: string;
}>) {
  return (
    <div className="rounded-2xl border border-border bg-bg p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text">{value}</p>
      {helper ? <p className="mt-2 text-sm text-muted">{helper}</p> : null}
    </div>
  );
}

function DetailSection({
  title,
  value,
  placeholder,
}: Readonly<{
  title: string;
  value: string;
  placeholder: string;
}>) {
  return (
    <div className="rounded-[24px] border border-border bg-bg p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
        {title}
      </p>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-text">
        {value || placeholder}
      </p>
    </div>
  );
}

function TabButton({
  label,
  isActive,
  onClick,
}: Readonly<{
  label: string;
  isActive: boolean;
  onClick: () => void;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border px-4 py-2.5 text-sm font-semibold transition ${
        isActive
          ? "border-primary-light bg-primary-light/10 text-primary"
          : "border-border bg-bg text-text hover:border-primary-light/30 hover:bg-primary-light/10"
      }`}
    >
      {label}
    </button>
  );
}

export function SpecificationsDetailPanel({
  selectedSource,
  selectedGroup,
  selectedSpecification,
  selectedSpecificationIds,
  selectedGroupPage,
  pageSize,
  activeTab,
  deletingSpecificationId,
  deletingSourceId,
  reparsingSourceId,
  importingSourceId,
  onSelectGroup,
  onSelectSpecification,
  onToggleSpecificationSelection,
  onTogglePageSelection,
  onClearSelection,
  onChangePage,
  onChangeTab,
  onOpenSpecificationEdit,
  onDeleteSpecification,
  onOpenSourceReview,
  onReparseSource,
  onImportSource,
  onDeleteSource,
}: Readonly<SpecificationsDetailPanelProps>) {
  if (!selectedSource) {
    return (
      <EmptyState
        icon={<SpecificationWorkspaceIcon />}
        title="Select a source to start drilling down"
        description="Use the tree on the left to move from source to grouped specs, then open a normalized specification only when you need the full detail."
      />
    );
  }

  if (!selectedGroup) {
    return (
      <SourceOverview
        selectedSource={selectedSource}
        onSelectGroup={onSelectGroup}
        deletingSourceId={deletingSourceId}
        reparsingSourceId={reparsingSourceId}
        importingSourceId={importingSourceId}
        onOpenSourceReview={onOpenSourceReview}
        onReparseSource={onReparseSource}
        onImportSource={onImportSource}
        onDeleteSource={onDeleteSource}
      />
    );
  }

  const totalSpecifications = selectedGroup.specifications.length;
  const totalPages = Math.max(1, Math.ceil(totalSpecifications / pageSize));
  const currentPage = Math.min(selectedGroupPage, totalPages);
  const startIndex = (currentPage - 1) * pageSize;
  const visibleSpecifications = selectedGroup.specifications.slice(
    startIndex,
    startIndex + pageSize
  );
  const visibleIds = visibleSpecifications.map((specification) => specification.id);
  const selectedOnPageCount = visibleIds.filter((id) =>
    selectedSpecificationIds.includes(id)
  ).length;
  const allOnPageSelected =
    visibleIds.length > 0 && selectedOnPageCount === visibleIds.length;

  return (
    <section className="space-y-6">
      <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="tag">{selectedSource.label}</Badge>
              <Badge variant={selectedSource.statusVariant}>
                {selectedSource.statusLabel}
              </Badge>
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-tight text-text">
              {selectedGroup.label}
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              Showing only the structured requirements in this grouped bucket. Open a row to inspect the detailed content and traceability below.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-bg px-4 py-3 text-sm text-muted">
            <p>
              {totalSpecifications} specification
              {totalSpecifications === 1 ? "" : "s"}
            </p>
            <p className="mt-1">{selectedGroup.subtitle}</p>
          </div>
        </div>

        <div className="mt-6 rounded-[24px] border border-border bg-bg p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                Normalized specifications
              </p>
              <p className="mt-1 text-sm text-muted">
                Compact list only. Description, steps, traceability, and processing details stay hidden until you open a spec.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
              <span>{selectedSpecificationIds.length} selected</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  onTogglePageSelection(visibleIds, !allOnPageSelected)
                }
                disabled={visibleIds.length === 0}
              >
                {allOnPageSelected ? "Unselect Page" : "Select Page"}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={onClearSelection}
                disabled={selectedSpecificationIds.length === 0}
              >
                Clear Selection
              </Button>
            </div>
          </div>

          {visibleSpecifications.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-border bg-surface p-5 text-sm text-muted">
              No structured requirements are available in this group yet.
            </div>
          ) : (
            <div className="mt-5 overflow-hidden rounded-[24px] border border-border bg-surface">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-bg">
                  <tr>
                    <th className="px-4 py-4 text-left">
                      <input
                        type="checkbox"
                        checked={allOnPageSelected}
                        onChange={(event) =>
                          onTogglePageSelection(visibleIds, event.target.checked)
                        }
                        className="h-4 w-4 rounded border-border text-primary focus:ring-primary-light"
                        aria-label="Select visible specifications"
                      />
                    </th>
                    <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      ID
                    </th>
                    <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Title
                    </th>
                    <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Type
                    </th>
                    <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Priority
                    </th>
                    <th className="px-4 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {visibleSpecifications.map((specification) => {
                    const presentation = getSpecificationPresentation(specification);
                    const isSelected =
                      selectedSpecification?.id === specification.id;
                    const isChecked = selectedSpecificationIds.includes(
                      specification.id
                    );

                    return (
                      <tr
                        key={specification.id}
                        className={`transition ${
                          isSelected ? "bg-primary-light/10" : "hover:bg-bg"
                        }`}
                      >
                        <td className="px-4 py-4 align-top">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() =>
                              onToggleSpecificationSelection(specification.id)
                            }
                            className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary-light"
                            aria-label={`Select ${specification.title}`}
                          />
                        </td>
                        <td className="px-4 py-4 align-top text-sm font-semibold text-text">
                          {presentation.identifier}
                        </td>
                        <td className="px-4 py-4 align-top">
                          <button
                            type="button"
                            onClick={() =>
                              onSelectSpecification(
                                selectedSource.key,
                                selectedGroup.key,
                                specification.id
                              )
                            }
                            className="text-left"
                          >
                            <p className="text-sm font-semibold tracking-tight text-text">
                              {specification.title}
                            </p>
                            <p className="mt-1 text-xs text-muted">
                              {specification.linked_test_case_count} linked case
                              {specification.linked_test_case_count === 1 ? "" : "s"} /{" "}
                              {formatDate(specification.updated_at)}
                            </p>
                          </button>
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-muted">
                          <Badge variant="tag">{presentation.typeLabel}</Badge>
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-muted">
                          <Badge
                            variant={getPriorityVariant(presentation.priorityLabel)}
                          >
                            {presentation.priorityLabel}
                          </Badge>
                        </td>
                        <td className="px-4 py-4 align-top text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() =>
                                onSelectSpecification(
                                  selectedSource.key,
                                  selectedGroup.key,
                                  specification.id
                                )
                              }
                            >
                              Open
                            </Button>
                            {specification.can_manage ? (
                              <>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() =>
                                    onOpenSpecificationEdit(specification)
                                  }
                                >
                                  Edit
                                </Button>
                                <Button
                                  variant="danger"
                                  size="sm"
                                  onClick={() =>
                                    onDeleteSpecification(specification)
                                  }
                                  isLoading={
                                    deletingSpecificationId === specification.id
                                  }
                                  loadingText="Deleting..."
                                >
                                  Delete
                                </Button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 ? (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted">
                Showing {startIndex + 1}-{Math.min(startIndex + pageSize, totalSpecifications)} of{" "}
                {totalSpecifications}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onChangePage(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <span className="rounded-2xl border border-border bg-surface px-4 py-2 text-sm font-semibold text-text">
                  Page {currentPage} / {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onChangePage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </article>

      {selectedSpecification ? (
        <SpecificationDetailTabs
          specification={selectedSpecification}
          selectedSource={selectedSource}
          activeTab={activeTab}
          deletingSpecificationId={deletingSpecificationId}
          onChangeTab={onChangeTab}
          onOpenSpecificationEdit={onOpenSpecificationEdit}
          onDeleteSpecification={onDeleteSpecification}
        />
      ) : (
        <article className="rounded-[28px] border border-dashed border-border bg-surface p-6 text-sm text-muted shadow-sm">
          Select a specification from the table to open its detailed content, test design, traceability, and processing tabs.
        </article>
      )}
    </section>
  );
}

function SourceOverview({
  selectedSource,
  deletingSourceId,
  reparsingSourceId,
  importingSourceId,
  onSelectGroup,
  onOpenSourceReview,
  onReparseSource,
  onImportSource,
  onDeleteSource,
}: Readonly<{
  selectedSource: SpecificationTreeSource;
  deletingSourceId: string | null;
  reparsingSourceId: string | null;
  importingSourceId: string | null;
  onSelectGroup: (sourceKey: string, groupKey: string) => void;
  onOpenSourceReview: (sourceId: string) => void;
  onReparseSource: (sourceId: string) => void;
  onImportSource: (sourceId: string) => void;
  onDeleteSource: (source: SpecificationSource) => void;
}>) {
  const source = selectedSource.source;
  const coveredSpecificationCount = selectedSource.groups.reduce(
    (sum, group) =>
      sum +
      group.specifications.filter(
        (specification) => specification.coverage_status === "covered"
      ).length,
    0
  );

  return (
    <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={selectedSource.statusVariant}>
              {selectedSource.statusLabel}
            </Badge>
            <Badge variant="tag">{selectedSource.subtitle}</Badge>
          </div>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-text">
            {selectedSource.label}
          </h2>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-muted">
            Start from the source summary, then choose a grouped spec to reveal only the normalized items that belong together.
          </p>
        </div>

        {source ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => onOpenSourceReview(source.id)}
            >
              Review Import
            </Button>
            {source.can_manage ? (
              <>
                <Button
                  variant="secondary"
                  onClick={() => onReparseSource(source.id)}
                  isLoading={reparsingSourceId === source.id}
                  loadingText="Parsing..."
                >
                  Reparse
                </Button>
                <Button
                  onClick={() => onImportSource(source.id)}
                  isLoading={importingSourceId === source.id}
                  loadingText="Importing..."
                  disabled={source.selected_record_count === 0}
                >
                  Import Selected
                </Button>
                <Button
                  variant="danger"
                  onClick={() => onDeleteSource(source)}
                  isLoading={deletingSourceId === source.id}
                  loadingText="Deleting..."
                >
                  Delete
                </Button>
              </>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Groups"
          value={selectedSource.groups.length}
          helper="Logical buckets shown in the tree."
        />
        <MetricCard
          label="Normalized specs"
          value={selectedSource.specificationCount}
          helper="Compact records derived from this source."
        />
        <MetricCard
          label="Covered specs"
          value={coveredSpecificationCount}
          helper="Specs already linked to test cases."
        />
        <MetricCard
          label={source ? "Parsed records" : "Standalone specs"}
          value={source ? source.record_count : selectedSource.specificationCount}
          helper={
            source
              ? `${source.selected_record_count} selected / ${source.imported_record_count} imported`
              : "Manual or directly created records."
          }
        />
      </div>

      {source?.parser_error ? (
        <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-500">
          {source.parser_error}
        </div>
      ) : null}

      <div className="mt-6 rounded-[24px] border border-border bg-bg p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Grouped specs
            </p>
            <p className="mt-1 text-sm text-muted">
              Choose a group to focus the normalized list before opening a detailed record.
            </p>
          </div>
        </div>

        {selectedSource.groups.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-border bg-surface p-5 text-sm text-muted">
            No grouped specifications are available under this source yet.
          </div>
        ) : (
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            {selectedSource.groups.map((group) => {
              const firstSpecification = group.specifications[0] ?? null;
              const presentation = firstSpecification
                ? getSpecificationPresentation(firstSpecification)
                : null;

              return (
                <button
                  key={group.key}
                  type="button"
                  onClick={() => onSelectGroup(selectedSource.key, group.key)}
                  className="rounded-[24px] border border-border bg-surface p-5 text-left transition hover:border-primary-light/30 hover:bg-primary-light/10"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold tracking-tight text-text">
                        {group.label}
                      </p>
                      <p className="mt-1 text-xs text-muted">{group.subtitle}</p>
                    </div>
                    <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                      {group.specifications.length} spec
                      {group.specifications.length === 1 ? "" : "s"}
                    </span>
                  </div>

                  {presentation ? (
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <Badge variant="tag">{presentation.typeLabel}</Badge>
                      <Badge variant={getPriorityVariant(presentation.priorityLabel)}>
                        {presentation.priorityLabel}
                      </Badge>
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </article>
  );
}

function SpecificationDetailTabs({
  specification,
  selectedSource,
  activeTab,
  deletingSpecificationId,
  onChangeTab,
  onOpenSpecificationEdit,
  onDeleteSpecification,
}: Readonly<{
  specification: Specification;
  selectedSource: SpecificationTreeSource;
  activeTab: SpecificationDetailTab;
  deletingSpecificationId: string | null;
  onChangeTab: (tab: SpecificationDetailTab) => void;
  onOpenSpecificationEdit: (specification: Specification) => void;
  onDeleteSpecification: (specification: Specification) => void;
}>) {
  const presentation = getSpecificationPresentation(specification);
  const traceabilityGroups = buildTraceabilityGroups(specification);
  const metadataEntries = Object.entries(presentation.fields);

  return (
    <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="tag">{presentation.identifier}</Badge>
            <Badge variant="tag">{presentation.typeLabel}</Badge>
            <Badge variant={getPriorityVariant(presentation.priorityLabel)}>
              {presentation.priorityLabel}
            </Badge>
            <Badge
              variant={
                specification.coverage_status === "covered" ? "verified" : "warm"
              }
            >
              {specification.coverage_status}
            </Badge>
          </div>
          <h3 className="mt-4 text-2xl font-semibold tracking-tight text-text">
            {specification.title}
          </h3>
          <p className="mt-2 text-sm text-muted">
            Source {selectedSource.label} / Updated {formatDate(specification.updated_at)}
          </p>
        </div>

        {specification.can_manage ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => onOpenSpecificationEdit(specification)}
            >
              Edit
            </Button>
            <Button
              variant="danger"
              onClick={() => onDeleteSpecification(specification)}
              isLoading={deletingSpecificationId === specification.id}
              loadingText="Deleting..."
            >
              Delete
            </Button>
          </div>
        ) : null}
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {[
          ["overview", "Overview"],
          ["normalized-content", "Normalized Content"],
          ["test-design", "Test Design"],
          ["traceability", "Traceability"],
          ["rag", "Segments"],
        ].map(([key, label]) => (
          <TabButton
            key={key}
            label={label}
            isActive={activeTab === key}
            onClick={() => onChangeTab(key as SpecificationDetailTab)}
          />
        ))}
      </div>

      {activeTab === "overview" ? (
        <div className="mt-6 space-y-5">
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard label="Requirement ID" value={presentation.identifier} />
            <MetricCard label="Type" value={presentation.typeLabel} />
            <MetricCard label="Priority" value={presentation.priorityLabel} />
            <MetricCard
              label="Version"
              value={presentation.versionLabel}
              helper={`${specification.chunk_count} processing segment${
                specification.chunk_count === 1 ? "" : "s"
              }`}
            />
          </div>

          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Overview
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Module
                </p>
                <p className="mt-2 text-sm font-semibold text-text">
                  {presentation.moduleLabel}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Section
                </p>
                <p className="mt-2 text-sm font-semibold text-text">
                  {presentation.sectionLabel}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Project
                </p>
                <p className="mt-2 text-sm font-semibold text-text">
                  {specification.project_name}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Source
                </p>
                <p className="mt-2 text-sm font-semibold text-text">
                  {specification.source_name ||
                    getSourceDisplayName(selectedSource.source) ||
                    "Standalone specification"}
                </p>
              </div>
            </div>
          </div>

          <DetailSection
            title="Summary"
            value={presentation.description}
            placeholder="No overview is available for this specification."
          />
        </div>
      ) : null}

      {activeTab === "normalized-content" ? (
        <div className="mt-6 space-y-4">
          <DetailSection
            title="Description"
            value={presentation.description}
            placeholder="No description is available."
          />
          <DetailSection
            title="Preconditions"
            value={presentation.preconditions}
            placeholder="No preconditions were captured."
          />
          <DetailSection
            title="Steps"
            value={presentation.steps}
            placeholder="No structured steps were captured."
          />
          <DetailSection
            title="Expected Result"
            value={presentation.expectedResult}
            placeholder="No expected result was captured."
          />
          <DetailSection
            title="Acceptance Criteria"
            value={presentation.acceptanceCriteria}
            placeholder="No acceptance criteria were captured."
          />
          <DetailSection
            title="Normalized Content"
            value={specification.content}
            placeholder="No normalized content is available."
          />
        </div>
      ) : null}

      {activeTab === "test-design" ? (
        <div className="mt-6 space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard
              label="Linked cases"
              value={specification.linked_test_case_count}
            />
            <MetricCard
              label="Linked scenarios"
              value={specification.linked_scenario_count}
            />
            <MetricCard
              label="Linked suites"
              value={specification.linked_suite_count}
            />
          </div>

          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Linked test cases
            </p>
            {specification.linked_test_cases.length === 0 ? (
              <p className="mt-4 text-sm text-muted">
                No test cases are linked to this specification yet.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {specification.linked_test_cases.map((testCase) => (
                  <div
                    key={testCase.id}
                    className="rounded-2xl border border-border bg-surface p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={
                          testCase.status === "passed" || testCase.status === "ready"
                            ? "verified"
                            : testCase.status === "failed" ||
                                testCase.status === "skipped"
                              ? "warm"
                              : "unverified"
                        }
                      >
                        {testCase.status}
                      </Badge>
                      <Badge
                        variant={
                          testCase.automation_status === "automated"
                            ? "automated"
                            : "tag"
                        }
                      >
                        {labelize(testCase.automation_status)}
                      </Badge>
                      <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                        v{testCase.version}
                      </span>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-text">
                      {testCase.title}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {testCase.suite_name} / {testCase.scenario_title}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "traceability" ? (
        <div className="mt-6 space-y-5">
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard label="Project" value={specification.project_name} />
            <MetricCard label="Team" value={specification.team_name} />
            <MetricCard
              label="Source"
              value={
                specification.source_name ||
                getSourceDisplayName(selectedSource.source) ||
                "Standalone"
              }
            />
            <MetricCard
              label="External ref"
              value={specification.external_reference || "-"}
            />
          </div>

          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Traceability map
            </p>
            {traceabilityGroups.length === 0 ? (
              <p className="mt-4 text-sm text-muted">
                No suite, scenario, or case traceability is available yet.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {traceabilityGroups.map((suiteGroup) => (
                  <div
                    key={suiteGroup.suiteId}
                    className="rounded-2xl border border-border bg-surface p-4"
                  >
                    <p className="text-sm font-semibold text-text">
                      {suiteGroup.suiteName}
                    </p>
                    <div className="mt-3 space-y-3">
                      {suiteGroup.scenarios.map((scenarioGroup) => (
                        <div
                          key={scenarioGroup.scenarioId}
                          className="rounded-2xl border border-border bg-bg p-4"
                        >
                          <p className="text-sm font-semibold text-text">
                            {scenarioGroup.scenarioTitle}
                          </p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {scenarioGroup.cases.map((testCase) => (
                              <span
                                key={testCase.id}
                                className="rounded-full border border-border bg-surface px-3 py-1 text-xs font-semibold text-text"
                              >
                                {testCase.title}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <details className="rounded-[24px] border border-border bg-bg p-5">
            <summary className="cursor-pointer text-sm font-semibold text-text">
              Metadata
            </summary>
            <div className="mt-4 space-y-3">
              {metadataEntries.length === 0 ? (
                <p className="text-sm text-muted">
                  No structured metadata was captured for this specification.
                </p>
              ) : (
                metadataEntries.map(([key, value]) => (
                  <div
                    key={key}
                    className="rounded-2xl border border-border bg-surface p-4"
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      {labelize(key)}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-text">
                      {value}
                    </p>
                  </div>
                ))
              )}
            </div>
          </details>
        </div>
      ) : null}

      {activeTab === "rag" ? (
        <div className="mt-6 space-y-5">
          <MetricCard
            label="Segments"
            value={specification.chunk_count}
            helper="Processing details stay collapsed until you explicitly expand them."
          />

          {specification.chunks.length === 0 ? (
            <div className="rounded-[24px] border border-dashed border-border bg-bg p-5 text-sm text-muted">
              No processing segments are stored for this specification yet.
            </div>
          ) : (
            <details className="rounded-[24px] border border-border bg-bg p-5">
              <summary className="cursor-pointer text-sm font-semibold text-text">
                Expand processing segments
              </summary>
              <div className="mt-4 space-y-3">
                {specification.chunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="rounded-2xl border border-border bg-surface p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="tag">{labelize(chunk.chunk_type)}</Badge>
                      <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                        Segment {chunk.chunk_index + 1}
                      </span>
                      <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                        {chunk.token_count} tokens
                      </span>
                      {chunk.component_tag ? (
                        <span className="rounded-full border border-primary-light/20 bg-tag-fill px-2.5 py-1 text-xs font-semibold text-primary">
                          {chunk.component_tag}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-text">
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      ) : null}
    </article>
  );
}
