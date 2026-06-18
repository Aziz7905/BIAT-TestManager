import { useMemo } from "react";
import { Badge, Button, EmptyState, Spinner } from "../../ui";
import type {
  SpecificationSourceDetail,
  SpecificationSourceRecord,
  SpecRegionMappingTarget,
} from "../../../types/specs";
import {
  formatDateTime,
  parserStatusColor,
  recordStatusColor,
  sourceTypeLabel,
} from "./shared";

interface SpecificationSourceDetailPaneProps {
  detail: SpecificationSourceDetail | null;
  loading: boolean;
  error: string | null;
  parsing: boolean;
  importing: boolean;
  deleting: boolean;
  deletingSelectedRecords: boolean;
  recordUpdatingIds: Record<string, boolean>;
  onParse: () => void;
  onDelete: () => void;
  onImportSelected: () => void;
  onDeleteSelectedRecords: () => void;
  onEditRecord: (record: SpecificationSourceRecord) => void;
  onMapRegion: (region: SpecRegionMappingTarget) => void;
  onOpenSpec: (specId: string) => void;
  onToggleRecordSelection: (record: SpecificationSourceRecord, selected: boolean) => void;
}

interface RegionGroup {
  id: string;
  structuralType: string;
  target: SpecRegionMappingTarget;
  records: SpecificationSourceRecord[];
}

function buildRegionGroups(records: SpecificationSourceRecord[]): RegionGroup[] {
  const order: string[] = [];
  const buckets = new Map<string, SpecificationSourceRecord[]>();

  for (const record of records) {
    const regionId = record.record_metadata?.structure?.region_id ?? record.id;
    if (!buckets.has(regionId)) {
      order.push(regionId);
      buckets.set(regionId, []);
    }
    buckets.get(regionId)!.push(record);
  }

  return order.map((id) => {
    const grouped = buckets.get(id)!;
    const structure = grouped[0]?.record_metadata?.structure;
    const review = grouped.find((record) => record.record_metadata?.review)?.record_metadata?.review;
    return {
      id,
      structuralType: structure?.structural_type ?? "unknown",
      records: grouped,
      target: {
        region_id: structure?.region_id ?? id,
        container: structure?.container ?? "",
        source_range: structure?.source_range ?? "",
        structural_type: structure?.structural_type ?? "unknown",
        columns: regionColumns(grouped),
        record_type: review?.record_type ?? null,
        column_mapping: review?.column_mapping ?? {},
      },
    };
  });
}

function regionColumns(records: SpecificationSourceRecord[]): string[] {
  const structure = records[0]?.record_metadata?.structure;
  const headerValues = structure?.header_candidates?.[0]?.values;
  if (headerValues && headerValues.length) {
    return headerValues.filter(Boolean);
  }
  const byColumn = new Map<number, string>();
  for (const record of records) {
    for (const cell of record.record_metadata?.structure?.row?.cells ?? []) {
      if (!byColumn.has(cell.column)) {
        byColumn.set(cell.column, cell.header_candidate);
      }
    }
  }
  if (byColumn.size) {
    return [...byColumn.entries()].sort((a, b) => a[0] - b[0]).map(([, label]) => label);
  }
  // Context regions carry the full grid; use its first row as the column labels.
  const firstGridRow = structure?.grid?.[0];
  if (firstGridRow) {
    return firstGridRow.map((cell) => cell.displayed_value || cell.raw_value).filter(Boolean);
  }
  return [];
}

function regionStatus(group: RegionGroup): { label: string; color: "yellow" | "green" | "slate" } {
  const review = group.records.find((record) => record.record_metadata?.review)?.record_metadata?.review;
  if (review?.record_type === "ignore") return { label: "Ignored", color: "slate" };
  if (group.structuralType === "table") {
    if (review?.confirmed) return { label: `Mapped: ${review.record_type}`, color: "green" };
    return { label: "Needs mapping", color: "yellow" };
  }
  return { label: review?.record_type ?? group.structuralType, color: "slate" };
}

export default function SpecificationSourceDetailPane({
  detail,
  loading,
  error,
  parsing,
  importing,
  deleting,
  deletingSelectedRecords,
  recordUpdatingIds,
  onParse,
  onDelete,
  onImportSelected,
  onDeleteSelectedRecords,
  onEditRecord,
  onMapRegion,
  onOpenSpec,
  onToggleRecordSelection,
}: SpecificationSourceDetailPaneProps) {
  const regionGroups = useMemo(
    () => (detail ? buildRegionGroups(detail.records) : []),
    [detail]
  );

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return <EmptyState title="Could not load this source" description={error} />;
  }

  if (!detail) {
    return (
      <EmptyState
        title="Select a source"
        description="Choose a specification source to review its records and import status."
      />
    );
  }

  const selectedCount = detail.records.filter((record) => record.is_selected).length;

  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="border-b border-slate-200 px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-lg font-semibold text-slate-900">{detail.name}</h3>
              <Badge label={sourceTypeLabel(detail.source_type)} />
              <Badge label={detail.parser_status} color={parserStatusColor(detail.parser_status)} />
            </div>
            <p className="mt-1 text-xs text-slate-400">{detail.project_name}</p>
            <p className="mt-1 text-sm text-slate-500">
              {detail.record_count} records • {selectedCount} selected • {detail.imported_record_count} imported
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="secondary" onClick={onParse} isLoading={parsing}>
              Parse
            </Button>
            <Button variant="danger" onClick={onDelete} isLoading={deleting}>
              Delete source
            </Button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <MetadataCard label="Updated" value={formatDateTime(detail.updated_at)} />
          <MetadataCard label="Uploaded by" value={detail.uploaded_by_name || "--"} />
          <MetadataCard label="File" value={detail.file_name || "--"} />
        </div>

        {(detail.source_url || detail.jira_issue_key || detail.parser_error) && (
          <div className="mt-4 space-y-2 text-sm text-slate-600">
            {detail.source_url && (
              <p>
                <span className="font-medium text-slate-800">URL:</span> {detail.source_url}
              </p>
            )}
            {detail.jira_issue_key && (
              <p>
                <span className="font-medium text-slate-800">Jira issue:</span> {detail.jira_issue_key}
              </p>
            )}
            {detail.parser_error && (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-red-700">
                {detail.parser_error}
              </p>
            )}
          </div>
        )}

        {detail.raw_text && (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Source text
            </p>
            <p className="line-clamp-6 whitespace-pre-wrap text-sm text-slate-700">{detail.raw_text}</p>
          </div>
        )}
      </div>

      <div className="px-6 py-5">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h4 className="text-sm font-semibold text-slate-900">Detected regions</h4>
            <p className="mt-0.5 text-xs text-slate-500">
              Confirm a type and column mapping for tables before import.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={onImportSelected} isLoading={importing} disabled={selectedCount === 0}>
              Import selected
            </Button>
            <Button
              variant="danger"
              onClick={onDeleteSelectedRecords}
              isLoading={deletingSelectedRecords}
              disabled={selectedCount === 0}
            >
              Delete selected
            </Button>
          </div>
        </div>

        {regionGroups.length === 0 ? (
          <EmptyState
            title="No records yet"
            description="Parse this source to populate records for review."
          />
        ) : (
          <div className="space-y-5">
            {regionGroups.map((group) => {
              const status = regionStatus(group);
              const isTable = group.structuralType === "table";
              return (
                <section key={group.id} className="rounded-lg border border-slate-200">
                  <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2.5">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="font-semibold text-slate-700">
                        {group.target.container || "Region"}
                      </span>
                      <span>{group.target.source_range}</span>
                      <Badge label={group.structuralType} />
                      <Badge label={status.label} color={status.color} />
                      <span>{group.records.length} {isTable ? "rows" : "block"}</span>
                    </div>
                    <Button size="sm" variant="secondary" onClick={() => onMapRegion(group.target)}>
                      {isTable ? "Map columns" : "Set type"}
                    </Button>
                  </header>

                  <table className="w-full text-sm">
                    <thead className="bg-white text-left text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Import</th>
                        <th className="px-4 py-3">Title</th>
                        <th className="px-4 py-3">Reference</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Specification</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {group.records.map((record) => (
                        <tr
                          key={record.id}
                          onClick={() => onEditRecord(record)}
                          className="cursor-pointer transition hover:bg-slate-50"
                        >
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={record.is_selected}
                              disabled={Boolean(recordUpdatingIds[record.id])}
                              onClick={(event) => event.stopPropagation()}
                              onChange={(event) => onToggleRecordSelection(record, event.target.checked)}
                              className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                            />
                          </td>
                          <td className="px-4 py-3">
                            <div className="max-w-[420px]">
                              <p className="truncate font-medium text-slate-900">{record.title}</p>
                              <p className="mt-0.5 truncate text-xs text-slate-500">{record.content}</p>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-slate-600">{record.external_reference || "--"}</td>
                          <td className="px-4 py-3">
                            <Badge
                              label={record.import_status}
                              color={recordStatusColor(record.import_status)}
                            />
                          </td>
                          <td className="px-4 py-3">
                            {record.linked_specification_id ? (
                              <button
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onOpenSpec(record.linked_specification_id ?? "");
                                }}
                                className="max-w-[200px] truncate text-left text-xs font-medium text-blue-600 hover:underline"
                                title={record.linked_specification_title ?? undefined}
                              >
                                {record.linked_specification_title ?? "View spec"}
                              </button>
                            ) : (
                              <span className="text-xs text-slate-400">--</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function MetadataCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-slate-800">{value}</p>
    </div>
  );
}
