import { useState } from "react";
import { getScenarioOverview } from "../../../api/testing";
import type { ScenarioOverview, SectionOverview } from "../../../types/testing";
import { Badge, Button } from "../../ui";
import type { TreeSelection } from "../../../types/tree";
import {
  ActivitySummary,
  automationTone,
  designTone,
  formatLabel,
  Header,
  LinkedSpecifications,
  MetricGrid,
  PanelSection,
  resultTone,
} from "./shared";

interface SectionOverviewPanelProps {
  overview: SectionOverview;
  onSelect?: (selection: TreeSelection) => void;
}

export default function SectionOverviewPanel({
  overview,
  onSelect,
}: SectionOverviewPanelProps) {
  const [expandedScenarioIds, setExpandedScenarioIds] = useState<Record<string, boolean>>({});
  const [scenarioDetailsById, setScenarioDetailsById] = useState<Record<string, ScenarioOverview>>({});
  const [loadingScenarioIds, setLoadingScenarioIds] = useState<Record<string, boolean>>({});

  async function toggleScenario(scenarioId: string) {
    const nextOpen = !expandedScenarioIds[scenarioId];
    setExpandedScenarioIds((current) => ({ ...current, [scenarioId]: nextOpen }));

    if (!nextOpen || scenarioDetailsById[scenarioId] || loadingScenarioIds[scenarioId]) {
      return;
    }

    setLoadingScenarioIds((current) => ({ ...current, [scenarioId]: true }));
    try {
      const detail = await getScenarioOverview(scenarioId);
      setScenarioDetailsById((current) => ({ ...current, [scenarioId]: detail }));
    } finally {
      setLoadingScenarioIds((current) => {
        const next = { ...current };
        delete next[scenarioId];
        return next;
      });
    }
  }

  return (
    <>
      <Header
        eyebrow={`${overview.context.project_name} / ${overview.context.suite_name || "Suite"}`}
        title={overview.name}
        subtitle={overview.context.parent_name ? `Inside ${overview.context.parent_name}` : "Top-level section"}
        badges={<Badge label={`${overview.counts.case_count ?? 0} cases`} color="slate" />}
      />

      <PanelSection title="Content snapshot">
        <MetricGrid
          items={[
            { label: "Child sections", value: overview.counts.child_section_count ?? 0 },
            { label: "Scenarios", value: overview.counts.scenario_count ?? 0 },
            { label: "Cases", value: overview.counts.case_count ?? 0 },
            { label: "Automated", value: overview.counts.automated_case_count ?? 0 },
          ]}
        />
      </PanelSection>

      <PanelSection title="Child sections">
        {overview.child_sections.length === 0 ? (
          <p className="text-sm text-slate-500">No child sections.</p>
        ) : (
          <div className="space-y-2">
            {overview.child_sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() =>
                  onSelect?.({
                    type: "section",
                    id: section.id,
                    parentId: overview.context.suite_id ?? undefined,
                  })
                }
                className="flex w-full items-center justify-between rounded-md border border-slate-200 px-3 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="text-sm font-medium text-slate-900">{section.name}</div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>{section.counts.child_section_count ?? 0} child sections</span>
                  <span>{section.counts.case_count ?? 0} cases</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </PanelSection>

      <PanelSection title={`Scenarios (${overview.scenarios.length})`}>
        {overview.scenarios.length === 0 ? (
          <p className="text-sm text-slate-500">No scenarios yet.</p>
        ) : (
          <div className="space-y-3">
            {overview.scenarios.map((scenario) => {
              const isExpanded = Boolean(expandedScenarioIds[scenario.id]);
              const detail = scenarioDetailsById[scenario.id];
              const isLoading = Boolean(loadingScenarioIds[scenario.id]);

              return (
                <div key={scenario.id} className="rounded-md border border-slate-200">
                  <div className="flex items-center justify-between gap-4 px-4 py-4">
                    <button
                      type="button"
                      onClick={() =>
                        onSelect?.({
                          type: "scenario",
                          id: scenario.id,
                          parentId: overview.id,
                        })
                      }
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="truncate text-lg font-semibold text-slate-900">
                        {scenario.title}
                      </div>
                      <div className="mt-1 text-sm text-slate-500">
                        {formatLabel(scenario.scenario_type)} / {formatLabel(scenario.priority)}
                      </div>
                    </button>

                    <div className="flex shrink-0 items-center gap-4">
                      <div className="text-right text-sm text-slate-500">
                        <div>{scenario.counts.case_count ?? 0} cases</div>
                        <div>{scenario.counts.automated_case_count ?? 0} automated</div>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void toggleScenario(scenario.id)}
                      >
                        {isExpanded ? "Hide cases" : "View cases"}
                      </Button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-slate-200 bg-slate-50/60 px-4 py-3">
                      {isLoading && <p className="text-sm text-slate-500">Loading test cases...</p>}

                      {!isLoading && detail && detail.cases.length === 0 && (
                        <p className="text-sm text-slate-500">No test cases under this scenario yet.</p>
                      )}

                      {!isLoading && detail && detail.cases.length > 0 && (
                        <div className="space-y-2">
                          {detail.cases.map((testCase) => (
                            <div
                              key={testCase.id}
                              className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 py-3"
                            >
                              <button
                                type="button"
                                onClick={() =>
                                  onSelect?.({
                                    type: "case",
                                    id: testCase.id,
                                    parentId: scenario.id,
                                  })
                                }
                                className="min-w-0 flex-1 text-left"
                              >
                                <div className="truncate text-sm font-medium text-slate-800">
                                  {testCase.title}
                                </div>
                              </button>

                              <div className="flex shrink-0 items-center gap-2">
                                <Badge
                                  label={formatLabel(testCase.design_status)}
                                  color={designTone(testCase.design_status)}
                                  dot
                                />
                                <Badge
                                  label={formatLabel(testCase.automation_status)}
                                  color={automationTone(testCase.automation_status)}
                                />
                                <Badge
                                  label={formatLabel(testCase.latest_result_status || "none")}
                                  color={resultTone(testCase.latest_result_status)}
                                  dot
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Linked specifications">
        <LinkedSpecifications items={overview.linked_specifications} />
      </PanelSection>

      <PanelSection title="Recent activity">
        <ActivitySummary snapshot={overview.recent_activity} />
      </PanelSection>
    </>
  );
}
