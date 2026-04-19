import type { CSSProperties } from "react";
import { useMemo } from "react";
import { Badge, Button, EmptyState, PaginationControls, Spinner } from "../../ui";
import type { PaginatedResponse } from "../../../types/common";
import type {
  CoverageStatus,
  SpecificationIndexStatus,
  SpecificationListItem,
  SpecificationSourceType,
} from "../../../types/specs";
import { coverageColor, indexStatusColor, matchesSpecSearch, sourceTypeLabel } from "./shared";

interface SpecificationListPaneProps {
  page: number;
  data: PaginatedResponse<SpecificationListItem> | null;
  loading: boolean;
  selectedSpecId: string | null;
  style?: CSSProperties;
  search: string;
  coverageFilter: CoverageStatus | "all";
  sourceTypeFilter: SpecificationSourceType | "all";
  indexStatusFilter: SpecificationIndexStatus | "all";
  onSearchChange: (value: string) => void;
  onCoverageFilterChange: (value: CoverageStatus | "all") => void;
  onSourceTypeFilterChange: (value: SpecificationSourceType | "all") => void;
  onIndexStatusFilterChange: (value: SpecificationIndexStatus | "all") => void;
  onSelect: (specId: string) => void;
  onDeleteSelected: () => void;
  onNext: () => void;
  onPrevious: () => void;
}

export default function SpecificationListPane({
  page,
  data,
  loading,
  selectedSpecId,
  style,
  search,
  coverageFilter,
  sourceTypeFilter,
  indexStatusFilter,
  onSearchChange,
  onCoverageFilterChange,
  onSourceTypeFilterChange,
  onIndexStatusFilterChange,
  onSelect,
  onDeleteSelected,
  onNext,
  onPrevious,
}: SpecificationListPaneProps) {
  const filteredResults = useMemo(() => {
    if (!data) return [];
    return data.results.filter((specification) => {
      if (!matchesSpecSearch(specification, search)) return false;
      if (coverageFilter !== "all" && specification.coverage_status !== coverageFilter) return false;
      if (sourceTypeFilter !== "all" && specification.source_type !== sourceTypeFilter) return false;
      if (indexStatusFilter !== "all" && specification.index_status !== indexStatusFilter) return false;
      return true;
    });
  }, [coverageFilter, data, indexStatusFilter, search, sourceTypeFilter]);

  return (
    <aside className="flex shrink-0 flex-col border-r border-slate-200 bg-white" style={style}>
      <div className="border-b border-slate-200 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Imported specs</h3>
            <p className="mt-0.5 text-xs text-slate-500">Coverage and traceability</p>
          </div>
          {selectedSpecId && (
            <Button size="sm" variant="secondary" onClick={onDeleteSelected}>
              Delete
            </Button>
          )}
        </div>

        <div className="mt-4 space-y-3">
          <input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search by title or reference"
            className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={coverageFilter}
              onChange={(event) => onCoverageFilterChange(event.target.value as CoverageStatus | "all")}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="all">All coverage</option>
              <option value="covered">Covered</option>
              <option value="uncovered">Uncovered</option>
            </select>
            <select
              value={indexStatusFilter}
              onChange={(event) =>
                onIndexStatusFilterChange(event.target.value as SpecificationIndexStatus | "all")
              }
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="all">All index status</option>
              <option value="pending">Pending</option>
              <option value="indexed">Indexed</option>
              <option value="failed">Failed</option>
              <option value="stale">Stale</option>
            </select>
            <select
              value={sourceTypeFilter}
              onChange={(event) =>
                onSourceTypeFilterChange(event.target.value as SpecificationSourceType | "all")
              }
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600 sm:col-span-2"
            >
              <option value="all">All source types</option>
              <option value="plain_text">Plain text</option>
              <option value="url">URL</option>
              <option value="jira_issue">Jira issue</option>
              <option value="pdf">PDF</option>
              <option value="docx">DOCX</option>
              <option value="xlsx">XLSX</option>
              <option value="csv">CSV</option>
              <option value="file_upload">File upload</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Spinner />
          </div>
        ) : filteredResults.length === 0 ? (
          <EmptyState
            title={data?.results.length ? "No specs match this filter" : "No imported specs"}
            description={
              data?.results.length
                ? "Try a different search or filter."
                : "Import records from the Sources view to build the requirement library."
            }
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredResults.map((specification) => {
              const selected = specification.id === selectedSpecId;
              return (
                <button
                  key={specification.id}
                  onClick={() => onSelect(specification.id)}
                  className={[
                    "w-full px-4 py-3 text-left transition hover:bg-slate-50",
                    selected ? "bg-blue-50" : "bg-white",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {specification.title}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {specification.external_reference || "No reference"}
                      </p>
                    </div>
                    <Badge
                      label={specification.coverage_status}
                      color={coverageColor(specification.coverage_status)}
                    />
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge label={sourceTypeLabel(specification.source_type)} />
                    <Badge
                      label={specification.index_status}
                      color={indexStatusColor(specification.index_status)}
                    />
                  </div>

                  <p className="mt-2 text-[11px] text-slate-500">
                    {specification.linked_test_case_count} linked test cases
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {data && (
        <PaginationControls
          page={page}
          totalCount={data.count}
          hasNext={Boolean(data.next)}
          hasPrevious={Boolean(data.previous)}
          itemLabel="specifications"
          onNext={onNext}
          onPrevious={onPrevious}
          className="border-t border-slate-200"
        />
      )}
    </aside>
  );
}
