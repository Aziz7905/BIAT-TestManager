import { Badge, Button, EmptyState, Spinner } from "../../ui";
import type { SpecificationSourceDetail, SpecificationSourceRecord } from "../../../types/specs";
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
  onOpenSpec: (specId: string) => void;
  onToggleRecordSelection: (record: SpecificationSourceRecord, selected: boolean) => void;
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
  onOpenSpec,
  onToggleRecordSelection,
}: SpecificationSourceDetailPaneProps) {
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
            <h4 className="text-sm font-semibold text-slate-900">Source records</h4>
            <p className="mt-0.5 text-xs text-slate-500">
              Review the parsed requirement rows before import.
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

        {detail.records.length === 0 ? (
          <EmptyState
            title="No records yet"
            description="Parse this source to populate records for review."
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Import</th>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">Section</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Specification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {detail.records.map((record) => (
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
                        onChange={(event) =>
                          onToggleRecordSelection(record, event.target.checked)
                        }
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
                    <td className="px-4 py-3 text-slate-600">{record.section_label || "--"}</td>
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
