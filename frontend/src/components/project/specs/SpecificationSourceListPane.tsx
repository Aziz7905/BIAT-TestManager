import type { CSSProperties } from "react";
import { Badge, Button, EmptyState, PaginationControls, Spinner } from "../../ui";
import type { PaginatedResponse } from "../../../types/common";
import type { SpecificationSourceListItem } from "../../../types/specs";
import { formatDateTime, parserStatusColor, sourceTypeLabel } from "./shared";

interface SpecificationSourceListPaneProps {
  page: number;
  data: PaginatedResponse<SpecificationSourceListItem> | null;
  loading: boolean;
  selectedSourceId: string | null;
  style?: CSSProperties;
  onSelect: (sourceId: string) => void;
  onCreate: () => void;
  onNext: () => void;
  onPrevious: () => void;
}

export default function SpecificationSourceListPane({
  page,
  data,
  loading,
  selectedSourceId,
  style,
  onSelect,
  onCreate,
  onNext,
  onPrevious,
}: SpecificationSourceListPaneProps) {
  return (
    <aside className="flex shrink-0 flex-col border-r border-slate-200 bg-white" style={style}>
      <div className="border-b border-slate-200 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Sources</h3>
            <p className="mt-0.5 text-xs text-slate-500">Ingest, parse, review, import</p>
          </div>
          <Button size="sm" onClick={onCreate}>
            New source
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Spinner />
          </div>
        ) : !data || data.results.length === 0 ? (
          <EmptyState
            title="No specification sources"
            description="Create the first source to start importing requirements."
            action={<Button onClick={onCreate}>Create source</Button>}
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {data.results.map((source) => {
              const selected = source.id === selectedSourceId;
              return (
                <button
                  key={source.id}
                  onClick={() => onSelect(source.id)}
                  className={[
                    "w-full px-4 py-3 text-left transition hover:bg-slate-50",
                    selected ? "bg-blue-50" : "bg-white",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{source.name}</p>
                      <p className="mt-0.5 text-xs text-slate-500">{sourceTypeLabel(source.source_type)}</p>
                    </div>
                    <Badge
                      label={source.parser_status}
                      color={parserStatusColor(source.parser_status)}
                    />
                  </div>

                  <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
                    <span>{source.record_count} records</span>
                    <span>•</span>
                    <span>{source.imported_record_count} imported</span>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400">
                    Updated {formatDateTime(source.updated_at)}
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
          itemLabel="sources"
          onNext={onNext}
          onPrevious={onPrevious}
          className="border-t border-slate-200"
        />
      )}
    </aside>
  );
}
