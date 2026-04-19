import { useState } from "react";
import type { ScenarioOverview, TreeCase } from "../../../types/testing";
import type { TreeSelection } from "../../../types/tree";
import { Badge, Button, EmptyState } from "../../ui";
import ScenarioEditModal from "../tree/ScenarioEditModal";
import {
  ActivitySummary,
  automationTone,
  designTone,
  formatLabel,
  Header,
  LinkedSpecifications,
  MetricGrid,
  PanelSection,
  priorityTone,
  resultTone,
} from "./shared";

interface ScenarioOverviewPanelProps {
  overview: ScenarioOverview;
  onSelect?: (selection: TreeSelection) => void;
  onEditCase?: (caseId: string) => void;
  onScenarioSaved?: () => void;
}

export default function ScenarioOverviewPanel({
  overview,
  onSelect,
  onEditCase,
  onScenarioSaved,
}: ScenarioOverviewPanelProps) {
  const [editing, setEditing] = useState(false);

  return (
    <>
      <Header
        eyebrow={`${overview.context.project_name} / ${overview.context.suite_name || "Suite"} / ${overview.context.section_name || "Section"}`}
        title={overview.title}
        subtitle={formatLabel(overview.scenario_type)}
        badges={
          <>
            <Badge label={formatLabel(overview.priority)} color={priorityTone(overview.priority)} />
            <Badge label={formatLabel(overview.polarity)} color="blue" />
            {overview.business_priority && (
              <Badge label={formatLabel(overview.business_priority)} color="slate" />
            )}
          </>
        }
        actions={
          <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
            Edit scenario
          </Button>
        }
      />

      {overview.description && (
        <PanelSection title="Intent">
          <p className="text-sm leading-6 text-slate-700">{overview.description}</p>
        </PanelSection>
      )}

      <PanelSection title={`Test cases (${overview.cases.length})`}>
        {overview.cases.length === 0 ? (
          <EmptyState
            title="No cases yet"
            description="Create the first executable case under this scenario from the tree."
          />
        ) : (
          <div className="space-y-2">
            {overview.cases.map((testCase) => (
              <CaseRow
                key={testCase.id}
                testCase={testCase}
                onOpen={() =>
                  onSelect?.({ type: "case", id: testCase.id, parentId: overview.id })
                }
                onEdit={() => onEditCase?.(testCase.id)}
              />
            ))}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Coverage">
        <MetricGrid
          items={[
            { label: "Cases", value: overview.coverage.case_count ?? 0 },
            { label: "Approved", value: overview.coverage.approved_case_count ?? 0 },
            { label: "Automated", value: overview.coverage.automated_case_count ?? 0 },
            { label: "Linked specs", value: overview.linked_specifications.length },
          ]}
        />
      </PanelSection>

      <PanelSection title="Linked specifications">
        <LinkedSpecifications items={overview.linked_specifications} />
      </PanelSection>

      <PanelSection title="Recent activity">
        <ActivitySummary snapshot={overview.execution_snapshot} />
      </PanelSection>

      <ScenarioEditModal
        open={editing}
        scenarioId={editing ? overview.id : null}
        sectionId={editing ? overview.context.section_id ?? null : null}
        onClose={() => setEditing(false)}
        onSaved={() => onScenarioSaved?.()}
      />
    </>
  );
}

interface CaseRowProps {
  testCase: TreeCase;
  onOpen: () => void;
  onEdit: () => void;
}

function CaseRow({ testCase, onOpen, onEdit }: CaseRowProps) {
  return (
    <div
      className="group flex items-center gap-3 rounded-md border border-slate-200 px-3 py-2.5 transition hover:border-blue-300 hover:bg-blue-50/30"
    >
      <button
        type="button"
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-3 text-left"
      >
        <span className={`h-2 w-2 shrink-0 rounded-full ${dotClass(testCase.design_status)}`} />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">
          {testCase.title}
        </span>
      </button>

      <div className="flex shrink-0 items-center gap-2">
        <Badge label={formatLabel(testCase.design_status)} color={designTone(testCase.design_status)} dot />
        <Badge label={formatLabel(testCase.automation_status)} color={automationTone(testCase.automation_status)} />
        <Badge
          label={formatLabel(testCase.latest_result_status || "none")}
          color={resultTone(testCase.latest_result_status)}
          dot
        />
        <button
          type="button"
          onClick={onEdit}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 opacity-0 transition hover:bg-slate-100 hover:text-slate-900 group-hover:opacity-100"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

function dotClass(status: string) {
  if (status === "approved") return "bg-emerald-500";
  if (status === "in_review") return "bg-blue-500";
  if (status === "archived") return "bg-slate-300";
  return "bg-amber-400";
}
