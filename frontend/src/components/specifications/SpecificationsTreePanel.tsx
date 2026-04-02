import { Badge } from "../ui";
import type { Specification, SpecificationSource } from "../../types/specs";
import type { SpecificationBadgeVariant } from "./presentation";
import {
  getPriorityVariant,
  getSpecificationPresentation,
} from "./presentation";

export interface SpecificationTreeGroup {
  key: string;
  sourceKey: string;
  sourceId: string | null;
  label: string;
  subtitle: string;
  specifications: Specification[];
}

export interface SpecificationTreeSource {
  key: string;
  sourceId: string | null;
  label: string;
  subtitle: string;
  statusLabel: string;
  statusVariant: SpecificationBadgeVariant;
  source: SpecificationSource | null;
  groups: SpecificationTreeGroup[];
  specificationCount: number;
}

interface SpecificationsTreePanelProps {
  sources: SpecificationTreeSource[];
  selectedSourceKey: string;
  selectedGroupKey: string;
  selectedSpecificationId: string;
  onSelectSource: (sourceKey: string) => void;
  onSelectGroup: (sourceKey: string, groupKey: string) => void;
  onSelectSpecification: (
    sourceKey: string,
    groupKey: string,
    specificationId: string
  ) => void;
}

export function SpecificationsTreePanel({
  sources,
  selectedSourceKey,
  selectedGroupKey,
  selectedSpecificationId,
  onSelectSource,
  onSelectGroup,
  onSelectSpecification,
}: Readonly<SpecificationsTreePanelProps>) {
  return (
    <aside className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
        Specification tree
      </p>
      <p className="mt-2 text-sm leading-6 text-muted">
        Navigate by source first, then drill into grouped specs and individual normalized records.
      </p>

      <div className="mt-6 space-y-4">
        {sources.map((source) => {
          const isActiveSource = selectedSourceKey === source.key;
          const hasActiveGroup = source.groups.some(
            (group) =>
              group.key === selectedGroupKey ||
              group.specifications.some(
                (specification) => specification.id === selectedSpecificationId
              )
          );
          const isExpanded = isActiveSource || hasActiveGroup;

          return (
            <div
              key={source.key}
              className={`rounded-[24px] border transition ${
                isActiveSource
                  ? "border-primary-light bg-primary-light/10"
                  : "border-border bg-bg"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectSource(source.key)}
                className="w-full px-4 py-4 text-left"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold tracking-tight text-text">
                      {source.label}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">
                      {source.subtitle}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Badge variant={source.statusVariant}>{source.statusLabel}</Badge>
                    <span className="rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-muted">
                      {source.specificationCount} spec
                      {source.specificationCount === 1 ? "" : "s"}
                    </span>
                  </div>
                </div>
              </button>

              {isExpanded ? (
                <div className="border-t border-border/70 px-4 py-4">
                  {source.groups.length === 0 ? (
                    <p className="text-sm text-muted">
                      No grouped specifications are available under this source yet.
                    </p>
                  ) : (
                    <div className="space-y-2 border-l border-border pl-4">
                      {source.groups.map((group) => {
                        const isActiveGroup = selectedGroupKey === group.key;
                        const hasActiveSpecification = group.specifications.some(
                          (specification) =>
                            specification.id === selectedSpecificationId
                        );
                        const isGroupExpanded = isActiveGroup || hasActiveSpecification;

                        return (
                          <div key={group.key} className="space-y-2">
                            <button
                              type="button"
                              onClick={() => onSelectGroup(source.key, group.key)}
                              className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                                isActiveGroup
                                  ? "border-primary-light bg-primary-light/10"
                                  : "border-border bg-surface hover:border-primary-light/30 hover:bg-primary-light/10"
                              }`}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <p className="text-sm font-semibold tracking-tight text-text">
                                    {group.label}
                                  </p>
                                  <p className="mt-1 text-xs text-muted">
                                    {group.subtitle}
                                  </p>
                                </div>
                                <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-[11px] font-semibold text-muted">
                                  {group.specifications.length}
                                </span>
                              </div>
                            </button>

                            {isGroupExpanded ? (
                              <div className="space-y-2 border-l border-border pl-4">
                                {group.specifications.map((specification) => {
                                  const isSelected =
                                    selectedSpecificationId === specification.id;
                                  const presentation =
                                    getSpecificationPresentation(specification);

                                  return (
                                    <button
                                      key={specification.id}
                                      type="button"
                                      onClick={() =>
                                        onSelectSpecification(
                                          source.key,
                                          group.key,
                                          specification.id
                                        )
                                      }
                                      className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                                        isSelected
                                          ? "border-primary bg-primary text-white"
                                          : "border-border bg-bg text-text hover:border-primary-light/30 hover:bg-primary-light/10"
                                      }`}
                                    >
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span
                                          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                                            isSelected
                                              ? "bg-white/15 text-white"
                                              : "bg-tag-fill text-primary"
                                          }`}
                                        >
                                          {presentation.identifier}
                                        </span>
                                        <Badge
                                          variant={
                                            presentation.priorityLabel !== "-"
                                              ? getPriorityVariant(
                                                  presentation.priorityLabel
                                                )
                                              : isSelected
                                                ? "automated"
                                                : "tag"
                                          }
                                        >
                                          {presentation.priorityLabel !== "-"
                                            ? presentation.priorityLabel
                                            : presentation.typeLabel}
                                        </Badge>
                                      </div>
                                      <p className="mt-2 text-sm font-semibold tracking-tight">
                                        {specification.title}
                                      </p>
                                      <p
                                        className={`mt-1 text-xs ${
                                          isSelected ? "text-white/80" : "text-muted"
                                        }`}
                                      >
                                        {presentation.typeLabel}
                                      </p>
                                    </button>
                                  );
                                })}
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
