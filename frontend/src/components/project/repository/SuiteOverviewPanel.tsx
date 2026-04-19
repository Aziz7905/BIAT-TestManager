import type { SuiteOverview } from "../../../types/testing";
import { Badge } from "../../ui";
import type { TreeSelection } from "../../../types/tree";
import {
  ActivitySummary,
  formatDate,
  Header,
  LinkedSpecifications,
  MetricGrid,
  PanelSection,
} from "./shared";

interface SuiteOverviewPanelProps {
  overview: SuiteOverview;
  onSelect?: (selection: TreeSelection) => void;
}

export default function SuiteOverviewPanel({
  overview,
  onSelect,
}: SuiteOverviewPanelProps) {
  return (
    <>
      <Header
        eyebrow={overview.context.project_name}
        title={overview.name}
        subtitle={overview.folder_path || "No folder path"}
        badges={
          <>
            {overview.specification && <Badge label={overview.specification.title} color="blue" />}
            <Badge label={`${overview.counts.case_count ?? 0} cases`} color="slate" />
          </>
        }
      />

      <PanelSection title="Suite overview">
        <MetricGrid
          items={[
            { label: "Sections", value: overview.counts.section_count ?? 0 },
            { label: "Scenarios", value: overview.counts.scenario_count ?? 0 },
            { label: "Cases", value: overview.counts.case_count ?? 0 },
            { label: "Automated", value: overview.counts.automated_case_count ?? 0 },
          ]}
        />
        {overview.description && (
          <p className="mt-4 text-sm leading-6 text-slate-600">{overview.description}</p>
        )}
      </PanelSection>

      <PanelSection title="Sections">
        {overview.sections.length === 0 ? (
          <p className="text-sm text-slate-500">No sections yet.</p>
        ) : (
          <div className="space-y-2">
            {overview.sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() =>
                  onSelect?.({
                    type: "section",
                    id: section.id,
                    parentId: overview.id,
                  })
                }
                className="flex w-full items-center justify-between rounded-md border border-slate-200 px-3 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="text-sm font-medium text-slate-900">{section.name}</div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>{section.counts.scenario_count ?? 0} scenarios</span>
                  <span>{section.counts.case_count ?? 0} cases</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Linked specifications">
        <LinkedSpecifications items={overview.linked_specifications} />
      </PanelSection>

      <PanelSection title="Recent activity">
        <ActivitySummary snapshot={overview.recent_activity} />
        <div className="mt-3 text-xs text-slate-500">
          Created by {overview.created_by_name || "Unknown"} on {formatDate(overview.created_at)}
        </div>
      </PanelSection>
    </>
  );
}
