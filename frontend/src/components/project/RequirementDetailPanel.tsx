/** Read-only detail panel for BA sources and normalized requirements in a project tree. */
import { Button } from "../Button";
import { LoadingSpinner } from "../LoadingSpinner";
import { Badge } from "../ui";
import type {
  Specification,
  SpecificationSourceDetail,
} from "../../types/specs";
import type { TestSuite } from "../../types/testing";
import type { RequirementTreeGroup } from "./RequirementsTreePanel";

interface RequirementDetailPanelProps {
  selectedGroup: RequirementTreeGroup | null;
  selectedSpecification: Specification | null;
  selectedSourceDetail: SpecificationSourceDetail | null;
  isSourceLoading: boolean;
  linkedSuites: TestSuite[];
  onOpenSuites: () => void;
  onOpenRequirement: (requirementId: string) => void;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  try {
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function buildTraceabilityGroups(specification: Specification) {
  const suites = new Map<
    string,
    {
      suiteId: string;
      suiteName: string;
      scenarios: Map<
        string,
        {
          scenarioId: string;
          scenarioTitle: string;
          cases: Specification["linked_test_cases"];
        }
      >;
    }
  >();

  specification.linked_test_cases.forEach((testCase) => {
    const suiteGroup =
      suites.get(testCase.suite_id) ??
      {
        suiteId: testCase.suite_id,
        suiteName: testCase.suite_name,
        scenarios: new Map(),
      };

    const scenarioGroup =
      suiteGroup.scenarios.get(testCase.scenario_id) ??
      {
        scenarioId: testCase.scenario_id,
        scenarioTitle: testCase.scenario_title,
        cases: [],
      };

    scenarioGroup.cases.push(testCase);
    suiteGroup.scenarios.set(testCase.scenario_id, scenarioGroup);
    suites.set(testCase.suite_id, suiteGroup);
  });

  return [...suites.values()]
    .map((suite) => ({
      ...suite,
      scenarios: [...suite.scenarios.values()].sort((left, right) =>
        left.scenarioTitle.localeCompare(right.scenarioTitle)
      ),
    }))
    .sort((left, right) => left.suiteName.localeCompare(right.suiteName));
}

export function RequirementDetailPanel({
  selectedGroup,
  selectedSpecification,
  selectedSourceDetail,
  isSourceLoading,
  linkedSuites,
  onOpenSuites,
  onOpenRequirement,
}: Readonly<RequirementDetailPanelProps>) {
  if (!selectedGroup) {
    return null;
  }

  if (selectedSpecification) {
    const traceabilityGroups = buildTraceabilityGroups(selectedSpecification);
    const matchedSourceRecord =
      selectedSourceDetail?.records.find(
        (record) => record.id === selectedSpecification.source_record_id
      ) ?? null;

    return (
      <section className="space-y-6">
        <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="tag">
                  {selectedSpecification.source_type.replaceAll("_", " ")}
                </Badge>
                {selectedSpecification.external_reference ? (
                  <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                    {selectedSpecification.external_reference}
                  </span>
                ) : null}
                {selectedSpecification.source_name ? (
                  <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                    Source: {selectedSpecification.source_name}
                  </span>
                ) : null}
                <Badge
                  variant={
                    selectedSpecification.coverage_status === "covered"
                      ? "verified"
                      : "warm"
                  }
                >
                  {selectedSpecification.coverage_status}
                </Badge>
              </div>
              <h3 className="mt-4 text-2xl font-semibold tracking-tight text-text">
                {selectedSpecification.title}
              </h3>
              <p className="mt-3 max-w-4xl text-sm leading-7 text-muted">
                Review the imported requirement here, confirm the business intent, and connect it to the suites, scenarios, and cases that verify it.
              </p>
            </div>
            <div className="text-right text-sm text-muted">
              <p>Version {selectedSpecification.version}</p>
              <p className="mt-1">Updated {formatDate(selectedSpecification.updated_at)}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_320px]">
            <div className="space-y-4">
              <div className="rounded-[24px] border border-border bg-bg p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  Requirement summary
                </p>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Module
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {selectedSpecification.qtest_preview.module || "-"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Requirement ID
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {selectedSpecification.qtest_preview.requirement_id ||
                        selectedSpecification.external_reference ||
                        "-"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Summary
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {selectedSpecification.qtest_preview.summary ||
                        selectedSpecification.title}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Section
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {selectedSpecification.qtest_preview.section || "-"}
                    </p>
                  </div>
                </div>
                <div className="mt-4 rounded-2xl border border-border bg-surface p-4">
                  <p className="whitespace-pre-wrap text-sm leading-7 text-text">
                    {selectedSpecification.qtest_preview.description ||
                      selectedSpecification.content}
                  </p>
                </div>
              </div>

              <div className="rounded-[24px] border border-border bg-bg p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  Full requirement text
                </p>
                <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-sm leading-7 text-text">
                  {selectedSpecification.content}
                </pre>
              </div>

              <div className="rounded-[24px] border border-border bg-bg p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  Coverage and traceability
                </p>
                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-border bg-surface p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Linked cases
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-text">
                      {selectedSpecification.linked_test_case_count}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border bg-surface p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Linked scenarios
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-text">
                      {selectedSpecification.linked_scenario_count}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border bg-surface p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      Linked suites
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-text">
                      {selectedSpecification.linked_suite_count}
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-[24px] border border-border bg-bg p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  Imported source record
                </p>
                {matchedSourceRecord ? (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-2xl border border-border bg-surface p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant={
                            matchedSourceRecord.import_status === "imported"
                              ? "verified"
                              : matchedSourceRecord.import_status === "failed"
                                ? "warm"
                                : "unverified"
                          }
                        >
                          {matchedSourceRecord.import_status}
                        </Badge>
                        {matchedSourceRecord.section_label ? (
                          <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                            {matchedSourceRecord.section_label}
                          </span>
                        ) : null}
                        {matchedSourceRecord.row_number ? (
                          <span className="rounded-full border border-border bg-bg px-2.5 py-1 text-xs font-semibold text-muted">
                            Row {matchedSourceRecord.row_number}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-3 text-sm font-semibold text-text">
                        {matchedSourceRecord.title}
                      </p>
                      <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-sm leading-6 text-text">
                        {matchedSourceRecord.content}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-muted">
                    No source record preview is available for this requirement.
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-[24px] border border-border bg-bg p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  Source context
                </p>
                {isSourceLoading ? (
                  <div className="mt-6 flex justify-center">
                    <LoadingSpinner size="lg" />
                  </div>
                ) : (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-2xl border border-border bg-surface p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                        Source file
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {selectedSourceDetail?.name || selectedSpecification.source_name || "-"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border bg-surface p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                        Imported records
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {selectedSourceDetail?.imported_record_count ?? "-"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border bg-surface p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                        Source type
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {selectedSourceDetail?.source_type.replaceAll("_", " ") ??
                          selectedSpecification.source_type.replaceAll("_", " ")}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border bg-surface p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                        Coverage
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {selectedSpecification.coverage_status === "covered"
                          ? "Covered by at least one test case"
                          : "Not linked to any test case yet"}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              <div className="rounded-[24px] border border-border bg-bg p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Linked test design
                    </p>
                    <p className="mt-1 text-sm text-muted">
                      Requirement coverage is shown the way QA teams use it: suite, scenario, then case.
                    </p>
                  </div>
                  <Button variant="secondary" size="sm" onClick={onOpenSuites}>
                    Open Suites
                  </Button>
                </div>
                <div className="mt-4 space-y-3">
                  {traceabilityGroups.length === 0 ? (
                    <p className="text-sm text-muted">
                      No test cases are linked to this requirement yet.
                    </p>
                  ) : (
                    traceabilityGroups.map((suiteGroup) => {
                      const matchingSuite =
                        linkedSuites.find((suite) => suite.id === suiteGroup.suiteId) ?? null;

                      return (
                        <div
                          key={suiteGroup.suiteId}
                          className="rounded-2xl border border-border bg-surface p-4"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            {matchingSuite ? (
                              <Badge variant="verified">
                                {matchingSuite.pass_rate}% pass rate
                              </Badge>
                            ) : null}
                            <Badge variant="tag">
                              {suiteGroup.scenarios.length} scenario
                              {suiteGroup.scenarios.length === 1 ? "" : "s"}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm font-semibold text-text">
                            {suiteGroup.suiteName}
                          </p>

                          <div className="mt-4 space-y-3">
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
                                    <div
                                      key={testCase.id}
                                      className="flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-surface px-3 py-2 text-xs"
                                    >
                                      <Badge
                                        variant={
                                          testCase.status === "passed" ||
                                          testCase.status === "ready"
                                            ? "verified"
                                            : testCase.status === "failed" ||
                                                testCase.status === "skipped"
                                              ? "warm"
                                              : "unverified"
                                        }
                                      >
                                        {testCase.status}
                                      </Badge>
                                      <span className="font-semibold text-text">
                                        {testCase.title}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        </article>
      </section>
    );
  }

  return (
    <article className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={selectedGroup.statusVariant}>{selectedGroup.statusLabel}</Badge>
            <Badge variant="tag">{selectedGroup.subtitle}</Badge>
          </div>
          <h3 className="mt-4 text-2xl font-semibold tracking-tight text-text">
            {selectedGroup.label}
          </h3>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-muted">
            This is the original BA-owned source file or imported requirement source. QA reviews it here and builds traceable test artifacts from it rather than editing it like a test case.
          </p>
        </div>
        {selectedSourceDetail ? (
          <p className="text-sm text-muted">Updated {formatDate(selectedSourceDetail.updated_at)}</p>
        ) : null}
      </div>

      {isSourceLoading ? (
        <div className="mt-8 flex justify-center">
          <LoadingSpinner size="lg" />
        </div>
      ) : selectedSourceDetail ? (
        <div className="mt-6 space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            {[
              ["Parsed records", selectedSourceDetail.record_count],
              ["Selected", selectedSourceDetail.selected_record_count],
              ["Imported", selectedSourceDetail.imported_record_count],
              ["Requirements created", selectedGroup.specifications.length],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-border bg-bg p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  {label}
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">{value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Parsed records
            </p>
            <div className="mt-4 space-y-3">
              {selectedSourceDetail.records.length === 0 ? (
                <p className="text-sm text-muted">No records were parsed from this source yet.</p>
              ) : (
                selectedSourceDetail.records.map((record) => (
                  <div key={record.id} className="rounded-2xl border border-border bg-surface p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">{record.title}</p>
                        <p className="mt-1 text-xs text-muted">
                          {record.section_label || "Unsectioned"}
                          {record.row_number ? ` - row ${record.row_number}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant={
                            record.import_status === "imported"
                              ? "verified"
                              : record.import_status === "failed"
                                ? "warm"
                                : "unverified"
                          }
                        >
                          {record.import_status}
                        </Badge>
                        {record.linked_specification_id ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => onOpenRequirement(record.linked_specification_id ?? "")}
                          >
                            Open Requirement
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">
                      {record.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-6 rounded-[24px] border border-dashed border-border bg-bg p-6 text-sm text-muted">
          This source has not been loaded yet.
        </div>
      )}
    </article>
  );
}
