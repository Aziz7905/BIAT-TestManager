import { useEffect, useMemo, useState } from "react";
import type { CaseWorkspace } from "../../../types/testing";
import type { AutomationScript, TestExecution } from "../../../types/automation";
import { getScripts } from "../../../api/automation/scripts";
import {
  createExecution,
  deleteExecution,
  getExecutions,
  startManualBrowser,
} from "../../../api/automation/executions";
import { Badge, Button, EmptyState, ErrorMessage, Spinner } from "../../ui";
import {
  CaseSummaryBadges,
  Header,
  LinkedSpecifications,
  MetricGrid,
  PanelSection,
  automationTone,
  executionStatusTone,
  formatDateTime,
  formatJson,
  formatLabel,
  resultTone,
} from "./shared";
import CaseScriptEditorModal from "../case-editor/CaseScriptEditorModal";

type CaseTab = "design" | "automation" | "history" | "code" | "runs";

const TAB_LABELS: Record<CaseTab, string> = {
  design: "Design",
  automation: "Automation Snapshot",
  history: "History",
  code: "Code",
  runs: "Runs",
};

interface CaseWorkspacePanelProps {
  readonly testCase: CaseWorkspace;
  readonly onEditCase?: (caseId: string) => void;
  readonly onViewExecution?: (executionId: string) => void;
}

export default function CaseWorkspacePanel({
  testCase,
  onEditCase,
  onViewExecution,
}: CaseWorkspacePanelProps) {
  const [tab, setTab] = useState<CaseTab>("design");

  // Code tab state
  const [scripts, setScripts] = useState<AutomationScript[]>([]);
  const [isLoadingScripts, setIsLoadingScripts] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isOpeningBrowser, setIsOpeningBrowser] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [scriptEditorOpen, setScriptEditorOpen] = useState(false);

  // Runs tab state
  const [executions, setExecutions] = useState<TestExecution[]>([]);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);

  const prettyTestData = useMemo(
    () => formatJson(testCase.design.test_data),
    [testCase.design.test_data]
  );

  useEffect(() => {
    setTab("design");
    setScripts([]);
    setExecutions([]);
    setRunError(null);
    setScriptEditorOpen(false);
  }, [testCase.id]);

  async function loadScripts() {
    setIsLoadingScripts(true);
    try {
      setScripts(await getScripts({ test_case: testCase.id }));
    } finally {
      setIsLoadingScripts(false);
    }
  }

  useEffect(() => {
    if (tab !== "code") return;
    void loadScripts();
  }, [tab, testCase.id]);

  useEffect(() => {
    if (tab !== "runs") return;
    setIsLoadingRuns(true);
    getExecutions({ test_case: testCase.id })
      .then(setExecutions)
      .finally(() => setIsLoadingRuns(false));
  }, [tab, testCase.id]);

  const activeScript = scripts.find((s) => s.is_active) ?? null;

  async function handleRun() {
    setIsRunning(true);
    setRunError(null);
    try {
      const execution = await createExecution({
        test_case: testCase.id,
        script: activeScript?.id ?? null,
      });
      setExecutions((prev) => [execution, ...prev]);
      onViewExecution?.(execution.id);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to start execution.";
      setRunError(msg);
    } finally {
      setIsRunning(false);
    }
  }

  async function handleOpenBrowser() {
    setIsOpeningBrowser(true);
    setRunError(null);
    try {
      const execution = await startManualBrowser({ test_case: testCase.id });
      setExecutions((prev) => [execution, ...prev]);
      onViewExecution?.(execution.id);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to open manual browser.";
      setRunError(msg);
    } finally {
      setIsOpeningBrowser(false);
    }
  }

  async function handleDeleteExecution(executionId: string) {
    if (!window.confirm("Delete this execution and its stored results?")) return;
    await deleteExecution(executionId);
    if (tab === "runs") {
      setExecutions((current) => current.filter((item) => item.id !== executionId));
    }
  }

  return (
    <>
      <Header
        eyebrow={`${testCase.context.project_name} / ${testCase.context.suite_name || "Suite"} / ${testCase.context.section_name || "Section"} / ${testCase.context.scenario_title || "Scenario"}`}
        title={testCase.title}
        subtitle={`Revision ${testCase.design.version}`}
        badges={<CaseSummaryBadges testCase={testCase} />}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {onViewExecution && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void handleOpenBrowser()}
                isLoading={isOpeningBrowser}
                loadingText="Opening"
              >
                Open browser
              </Button>
            )}
            {onEditCase && (
              <Button variant="secondary" size="sm" onClick={() => onEditCase(testCase.id)}>
                Edit
              </Button>
            )}
          </div>
        }
      />

      <div className="border-b border-slate-200 px-6">
        <div className="flex flex-wrap gap-2 py-3">
          {(Object.keys(TAB_LABELS) as CaseTab[]).map((key) => (
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
              {TAB_LABELS[key]}
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
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-500">{result.duration_ms} ms</span>
                      {onViewExecution && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onViewExecution(result.execution_id)}
                        >
                          View
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </PanelSection>
        </>
      )}

      {tab === "code" && (
        <PanelSection
          title="Active script"
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void handleOpenBrowser()}
                isLoading={isOpeningBrowser}
                loadingText="Opening"
              >
                Open browser
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setScriptEditorOpen(true)}
                disabled={isLoadingScripts}
              >
                {activeScript ? "Edit code" : "Add code"}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleRun}
                isLoading={isRunning}
                loadingText="Starting…"
                disabled={isRunning || isLoadingScripts || !activeScript}
              >
                Run
              </Button>
            </div>
          }
        >
          {runError && (
            <div className="mb-4">
              <ErrorMessage message={runError} onDismiss={() => setRunError(null)} />
            </div>
          )}

          {isLoadingScripts && (
            <div className="flex justify-center py-8">
              <Spinner size="md" />
            </div>
          )}
          {!isLoadingScripts && activeScript && (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                  {activeScript.framework}
                </span>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                  {activeScript.language}
                </span>
                <span className="text-xs text-slate-400">
                  v{activeScript.script_version} · {formatDateTime(activeScript.created_at)}
                </span>
              </div>
              <pre className="overflow-x-auto rounded-md border border-slate-200 bg-slate-950 px-4 py-4 text-xs leading-relaxed text-slate-100">
                {activeScript.script_content}
              </pre>
            </>
          )}
          {!isLoadingScripts && !activeScript && (
            <EmptyState
              title="No active script"
              description="No active automation script is linked to this test case."
            />
          )}

          {!isLoadingScripts && scripts.some((s) => !s.is_active) && (
            <div className="mt-6">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Inactive scripts
              </h4>
              <div className="space-y-2">
                {scripts
                  .filter((s) => !s.is_active)
                  .map((script) => (
                    <div
                      key={script.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-500"
                    >
                      <span>
                        {script.framework} / {script.language} · v{script.script_version}
                      </span>
                      <span className="text-xs">{formatDateTime(script.created_at)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </PanelSection>
      )}

      {tab === "runs" && (
        <PanelSection title="Execution history">
          {isLoadingRuns && (
            <div className="flex justify-center py-8">
              <Spinner size="md" />
            </div>
          )}
          {!isLoadingRuns && executions.length === 0 && (
            <EmptyState
              title="No executions yet"
              description="Run this test case to see execution history here."
            />
          )}
          {!isLoadingRuns && executions.length > 0 && (
            <div className="space-y-2">
              {executions.map((execution) => (
                <div
                  key={execution.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-3"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge
                      label={formatLabel(execution.status)}
                      color={executionStatusTone(execution.status)}
                      dot
                    />
                    <span className="text-sm text-slate-700">
                      {formatDateTime(execution.started_at)}
                    </span>
                    <span className="text-xs text-slate-400">
                      {execution.browser} · {formatLabel(execution.trigger_type)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">
                      {execution.duration_ms == null ? "—" : `${execution.duration_ms} ms`}
                    </span>
                    {onViewExecution && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onViewExecution(execution.id)}
                      >
                        View
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => void handleDeleteExecution(execution.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </PanelSection>
      )}

      <CaseScriptEditorModal
        open={scriptEditorOpen}
        testCaseId={testCase.id}
        script={activeScript}
        onClose={() => setScriptEditorOpen(false)}
        onSaved={loadScripts}
      />
    </>
  );
}
