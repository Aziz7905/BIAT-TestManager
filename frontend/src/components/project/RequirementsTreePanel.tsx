/** Source-aware requirements tree for navigating BA files and normalized specs. */
import { Badge } from "../ui";
import type { Specification, SpecificationSource } from "../../types/specs";

export interface RequirementTreeGroup {
  key: string;
  label: string;
  subtitle: string;
  statusLabel: string;
  statusVariant: "tag" | "unverified" | "verified" | "automated" | "warm";
  source: SpecificationSource | null;
  specifications: Specification[];
}

interface RequirementsTreePanelProps {
  groups: RequirementTreeGroup[];
  selectedGroupKey: string;
  selectedSpecificationId: string;
  onSelectGroup: (groupKey: string) => void;
  onSelectSpecification: (groupKey: string, specificationId: string) => void;
  embedded?: boolean;
}

function renderGroupStatusLabel(specification: Specification): string {
  if (specification.linked_test_case_count > 0) {
    return `${specification.linked_test_case_count} linked case${
      specification.linked_test_case_count === 1 ? "" : "s"
    }`;
  }

  return "No linked cases";
}

export function RequirementsTreePanel({
  groups,
  selectedGroupKey,
  selectedSpecificationId,
  onSelectGroup,
  onSelectSpecification,
  embedded = false,
}: Readonly<RequirementsTreePanelProps>) {
  const content = (
    <>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
        Requirements tree
      </p>
      <p className="mt-2 text-sm leading-6 text-muted">
        Browse BA sources first, then open the requirement records created from each source.
      </p>

      <div className="mt-6 space-y-3">
        {groups.map((group) => {
          const isActiveGroup = selectedGroupKey === group.key;

          return (
            <div
              key={group.key}
              className={`overflow-hidden rounded-[24px] border transition ${
                isActiveGroup
                  ? "border-primary-light bg-primary-light/10"
                  : "border-border bg-bg"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectGroup(group.key)}
                className="w-full px-4 py-3 text-left"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold tracking-tight text-text">
                      {group.label}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">
                      {group.subtitle}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Badge variant={group.statusVariant}>{group.statusLabel}</Badge>
                    <span className="rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-muted">
                      {group.specifications.length} requirement
                      {group.specifications.length === 1 ? "" : "s"}
                    </span>
                  </div>
                </div>
              </button>

              {isActiveGroup ? (
                <div className="border-t border-border/70 px-4 py-3">
                  {group.specifications.length === 0 ? (
                    <p className="text-sm text-muted">
                      No requirements are available under this source yet.
                    </p>
                  ) : (
                    <div className="space-y-2 border-l border-border/80 pl-4">
                      {group.specifications.map((specification) => {
                        const isSelected = selectedSpecificationId === specification.id;
                        const referenceLabel =
                          specification.external_reference ||
                          specification.qtest_preview.requirement_id ||
                          "Requirement";
                        const secondaryLabel =
                          specification.external_reference &&
                          specification.title !== specification.external_reference
                            ? specification.title
                            : specification.qtest_preview.section ||
                              specification.source_name ||
                              "Imported requirement";

                        return (
                          <button
                            key={specification.id}
                            type="button"
                            onClick={() =>
                              onSelectSpecification(group.key, specification.id)
                            }
                            className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                              isSelected
                                ? "border-primary bg-primary text-white"
                                : "border-border bg-surface text-text hover:border-primary-light/30 hover:bg-primary-light/10"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span
                                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                                      isSelected
                                        ? "bg-white/15 text-white"
                                        : "bg-tag-fill text-primary"
                                    }`}
                                  >
                                    {referenceLabel}
                                  </span>
                                  <Badge
                                    variant={
                                      specification.coverage_status === "covered"
                                        ? isSelected
                                          ? "automated"
                                          : "verified"
                                        : isSelected
                                          ? "automated"
                                          : "warm"
                                    }
                                  >
                                    {specification.coverage_status}
                                  </Badge>
                                </div>
                                <p className="mt-2 truncate text-sm font-semibold tracking-tight">
                                  {secondaryLabel}
                                </p>
                                <p
                                  className={`mt-1 text-xs ${
                                    isSelected ? "text-white/80" : "text-muted"
                                  }`}
                                >
                                  {renderGroupStatusLabel(specification)}
                                  {specification.qtest_preview.section
                                    ? ` / ${specification.qtest_preview.section}`
                                    : ""}
                                </p>
                              </div>
                              <span
                                className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${
                                  isSelected ? "text-white/80" : "text-muted"
                                }`}
                              >
                                {specification.source_type.replaceAll("_", " ")}
                              </span>
                            </div>
                          </button>
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
    </>
  );

  if (embedded) {
    return <div>{content}</div>;
  }

  return (
    <aside className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
      {content}
    </aside>
  );
}
