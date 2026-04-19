import { useEffect, useMemo, useState } from "react";
import type { CaseWorkspace } from "../../../types/testing";
import { Badge, Button } from "../../ui";
import {
  CaseSummaryBadges,
  Header,
  LinkedSpecifications,
  MetricGrid,
  PanelSection,
  automationTone,
  formatDateTime,
  formatJson,
  formatLabel,
  resultTone,
} from "./shared";

type CaseTab = "design" | "automation" | "history";

interface CaseWorkspacePanelProps {
  testCase: CaseWorkspace;
  onEditCase?: (caseId: string) => void;
}

export default function CaseWorkspacePanel({
  testCase,
  onEditCase,
}: CaseWorkspacePanelProps) {
  const [tab, setTab] = useState<CaseTab>("design");

  useEffect(() => {
    setTab("design");
  }, [testCase.id]);

  const prettyTestData = useMemo(
    () => formatJson(testCase.design.test_data),
    [testCase.design.test_data]
  );

  return (
    <>
      <Header
        eyebrow={`${testCase.context.project_name} / ${testCase.context.suite_name || "Suite"} / ${testCase.context.section_name || "Section"} / ${testCase.context.scenario_title || "Scenario"}`}
        title={testCase.title}
        subtitle={`Revision ${testCase.design.version}`}
        badges={<CaseSummaryBadges testCase={testCase} />}
        actions={
          onEditCase ? (
            <Button variant="secondary" size="sm" onClick={() => onEditCase(testCase.id)}>
              Edit
            </Button>
          ) : undefined
        }
      />

      <div className="border-b border-slate-200 px-6">
        <div className="flex flex-wrap gap-2 py-3">
          {(["design", "automation", "history"] as CaseTab[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                tab === key
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {key === "design" ? "Design" : key === "automation" ? "Automation Snapshot" : "History"}
            </button>
          ))}
        </div>
      </div>

      {tab === "design" && (
        <>
          <PanelSection title="Expected result">
            <p className="text-sm leading-6 text-slate-700">{testCase.design.expected_result}</p>
          </PanelSection>

          <PanelSection title="Preconditions">
            <p className="text-sm leading-6 text-slate-700">
              {testCase.design.preconditions || "No preconditions recorded."}
            </p>
          </PanelSection>

          <PanelSection title="Steps">
            {testCase.design.steps.length === 0 ? (
              <p className="text-sm text-slate-500">No steps yet.</p>
            ) : (
              <div className="space-y-3">
                {testCase.design.steps.map((step, index) => (
                  <div
                    key={`${step.step}-${index}`}
                    className="grid grid-cols-1 gap-3 rounded-md border border-slate-200 px-3 py-3 md:grid-cols-[48px_minmax(0,1fr)_minmax(0,1fr)]"
                  >
                    <div className="text-sm font-semibold text-slate-400">{index + 1}</div>
                    <div>
                      <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                        Step
                      </div>
                      <div className="text-sm text-slate-700">{step.step || "-"}</div>
                    </div>
                    <div>
                      <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                        Outcome
                      </div>
                      <div className="text-sm text-slate-700">{step.outcome || "-"}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </PanelSection>

          <PanelSection title="Execution defaults">
            <MetricGrid
              items={[
                {
                  label: "Automation status",
                  value: (
                    <Badge
                      label={formatLabel(testCase.design.automation_status)}
                      color={automationTone(testCase.design.automation_status)}
                    />
                  ),
                },
                { label: "On failure", value: formatLabel(testCase.design.on_failure) },
                { label: "Timeout", value: `${testCase.design.timeout_ms} ms` },
                { label: "Revision", value: `v${testCase.design.version}` },
              ]}
            />
          </PanelSection>

          <PanelSection title="Test data">
            {prettyTestData ? (
              <pre className="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700">
                {prettyTestData}
              </pre>
            ) : (
              <p className="text-sm text-slate-500">No structured test data.</p>
            )}
          </PanelSection>

          <PanelSection title="Linked specifications">
            <LinkedSpecifications items={testCase.design.linked_specifications} />
          </PanelSection>
        </>
      )}

      {tab === "automation" && (
        <>
          <PanelSection title="Automation status">
            <MetricGrid
              items={[
                {
                  label: "Status",
                  value: (
                    <Badge
                      label={formatLabel(testCase.design.automation_status)}
                      color={automationTone(testCase.design.automation_status)}
                    />
                  ),
                },
                { label: "Active scripts", value: testCase.automation.active_script_count },
                {
                  label: "Runnable frameworks",
                  value: testCase.automation.runnable_frameworks.length || 0,
                },
                { label: "Artifacts", value: testCase.automation.artifact_count },
              ]}
            />
          </PanelSection>

          <PanelSection title="Latest execution">
            {testCase.automation.latest_execution ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-md border border-slate-200 px-3 py-3">
                  <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    Status
                  </div>
                  <div className="mt-1">
                    <Badge
                      label={formatLabel(testCase.automation.latest_execution.status)}
                      color={resultTone(testCase.automation.latest_execution.status)}
                      dot
                    />
                  </div>
                </div>
                <div className="rounded-md border border-slate-200 px-3 py-3">
                  <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    Started
                  </div>
                  <div className="mt-1 text-sm text-slate-700">
                    {formatDateTime(testCase.automation.latest_execution.started_at)}
                  </div>
                </div>
                <div className="rounded-md border border-slate-200 px-3 py-3">
                  <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    Duration
                  </div>
                  <div className="mt-1 text-sm text-slate-700">
                    {testCase.automation.latest_execution.duration_ms ?? 0} ms
                  </div>
                </div>
                <div className="rounded-md border border-slate-200 px-3 py-3">
                  <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    Runtime
                  </div>
                  <div className="mt-1 text-sm text-slate-700">
                    {testCase.automation.latest_execution.framework || "Unknown"} /{" "}
                    {testCase.automation.latest_execution.browser}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No execution yet.</p>
            )}
          </PanelSection>

          <PanelSection title="Automation linkage">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-md border border-slate-200 px-3 py-3 text-sm text-slate-700">
                {testCase.automation.has_active_script
                  ? "Active automation is linked."
                  : "No active automation linked yet."}
              </div>
              <div className="rounded-md border border-slate-200 px-3 py-3 text-sm text-slate-700">
                Frameworks:{" "}
                {testCase.automation.runnable_frameworks.length > 0
                  ? testCase.automation.runnable_frameworks.join(", ")
                  : "None"}
              </div>
              <div className="rounded-md border border-slate-200 px-3 py-3 text-sm text-slate-700">
                Last artifact: {formatDateTime(testCase.automation.last_artifact_at)}
              </div>
            </div>
          </PanelSection>
        </>
      )}

      {tab === "history" && (
        <>
          <PanelSection title="Version history">
            {testCase.history.version_history.length === 0 ? (
              <p className="text-sm text-slate-500">No revision history yet.</p>
            ) : (
              <div className="overflow-hidden rounded-md border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left">
                    <tr>
                      <th className="px-3 py-2 text-xs font-semibold text-slate-500">Version</th>
                      <th className="px-3 py-2 text-xs font-semibold text-slate-500">Created by</th>
                      <th className="px-3 py-2 text-xs font-semibold text-slate-500">Created at</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {testCase.history.version_history.map((item) => (
                      <tr key={item.id}>
                        <td className="px-3 py-3 text-slate-800">v{item.version_number}</td>
                        <td className="px-3 py-3 text-slate-600">{item.created_by_name || "Unknown"}</td>
                        <td className="px-3 py-3 text-slate-600">{formatDateTime(item.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </PanelSection>

          <PanelSection title="Recent results">
            {testCase.history.recent_results.length === 0 ? (
              <p className="text-sm text-slate-500">No recent results yet.</p>
            ) : (
              <div className="space-y-2">
                {testCase.history.recent_results.map((result) => (
                  <div
                    key={`${result.execution_id}-${result.created_at}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-3"
                  >
                    <div className="flex items-center gap-2">
                      <Badge label={formatLabel(result.status)} color={resultTone(result.status)} dot />
                      <span className="text-sm text-slate-700">{formatDateTime(result.created_at)}</span>
                    </div>
                    <div className="text-xs text-slate-500">{result.duration_ms} ms</div>
                  </div>
                ))}
              </div>
            )}
          </PanelSection>
        </>
      )}
    </>
  );
}
