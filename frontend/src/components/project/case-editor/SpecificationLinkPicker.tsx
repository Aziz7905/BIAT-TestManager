import { useEffect, useMemo, useState } from "react";
import { getSpecificationsPage } from "../../../api/specs";
import type { PaginatedResponse } from "../../../types/common";
import type { SpecificationListItem } from "../../../types/specs";
import type { LinkedSpec } from "../../../types/testing";
import { Badge, Button, PaginationControls, Spinner } from "../../ui";
import { coverageColor, matchesSpecSearch, sourceTypeLabel } from "../specs/shared";

interface SpecificationLinkPickerProps {
  projectId: string;
  selectedSpecifications: LinkedSpec[];
  onChange: (items: LinkedSpec[]) => void;
}

function toLinkedSpec(specification: SpecificationListItem): LinkedSpec {
  return {
    id: specification.id,
    title: specification.title,
    external_reference: specification.external_reference,
    source_type: specification.source_type,
  };
}

export default function SpecificationLinkPicker({
  projectId,
  selectedSpecifications,
  onChange,
}: SpecificationLinkPickerProps) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<PaginatedResponse<SpecificationListItem> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !projectId) return;

    let cancelled = false;
    setLoading(true);

    getSpecificationsPage(projectId, page)
      .then((response) => {
        if (!cancelled) {
          setData(response);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, page, projectId]);

  const selectedIds = useMemo(
    () => new Set(selectedSpecifications.map((specification) => specification.id)),
    [selectedSpecifications]
  );

  const visibleResults = useMemo(() => {
    if (!data) return [];
    return data.results.filter((specification) => matchesSpecSearch(specification, search));
  }, [data, search]);

  function toggleSpecification(specification: SpecificationListItem) {
    const next = selectedIds.has(specification.id)
      ? selectedSpecifications.filter((item) => item.id !== specification.id)
      : [...selectedSpecifications, toLinkedSpec(specification)];
    onChange(next);
  }

  return (
    <div className="rounded-md border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Linked specifications</h3>
          <p className="mt-1 text-xs text-slate-500">
            Keep traceability on the case without turning this editor into a specs page.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setOpen((current) => !current)}>
          {open ? "Hide browser" : "Browse specs"}
        </Button>
      </div>

      {selectedSpecifications.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No linked specifications yet.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {selectedSpecifications.map((specification) => (
            <div
              key={specification.id}
              className="flex items-start justify-between gap-3 rounded-md border border-slate-200 px-3 py-2"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-slate-900">
                  {specification.title}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {specification.external_reference ||
                    specification.source_type.replaceAll("_", " ")}
                </div>
              </div>
              <button
                type="button"
                onClick={() =>
                  onChange(selectedSpecifications.filter((item) => item.id !== specification.id))
                }
                className="rounded-md px-2 py-1 text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div className="mt-4 rounded-md border border-slate-200">
          <div className="border-b border-slate-200 p-3">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter current page by title or reference"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div className="max-h-72 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Spinner />
              </div>
            ) : visibleResults.length === 0 ? (
              <p className="px-3 py-6 text-sm text-slate-500">
                {data?.results.length
                  ? "No specifications match this filter on the current page."
                  : "No imported specifications yet."}
              </p>
            ) : (
              <div className="divide-y divide-slate-100">
                {visibleResults.map((specification) => {
                  const selected = selectedIds.has(specification.id);
                  return (
                    <label
                      key={specification.id}
                      className="flex cursor-pointer items-start gap-3 px-3 py-3 hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSpecification(specification)}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="truncate text-sm font-medium text-slate-900">
                            {specification.title}
                          </div>
                          <Badge
                            label={specification.coverage_status}
                            color={coverageColor(specification.coverage_status)}
                          />
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {specification.external_reference || "No reference"}
                        </div>
                        <div className="mt-2 text-[11px] text-slate-500">
                          {sourceTypeLabel(specification.source_type)} •{" "}
                          {specification.linked_test_case_count} linked cases
                        </div>
                      </div>
                    </label>
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
              onNext={() => setPage((current) => current + 1)}
              onPrevious={() => setPage((current) => Math.max(1, current - 1))}
              className="border-t border-slate-200"
            />
          )}
        </div>
      )}
    </div>
  );
}
