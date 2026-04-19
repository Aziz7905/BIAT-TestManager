import type { ProjectRepositoryOverview } from "../../../types/testing";
import type { TreeSelection } from "../../../types/tree";
import {
  ActivitySummary,
  Header,
  PanelSection,
  RecentRunItem,
  SummaryBreakdown,
} from "./shared";

interface ProjectOverviewPanelProps {
  overview: ProjectRepositoryOverview;
  onSelect?: (selection: TreeSelection) => void;
}

export default function ProjectOverviewPanel({
  overview,
  onSelect,
}: ProjectOverviewPanelProps) {
  return (
    <>
      <Header
        eyebrow="Repository overview"
        title={overview.project.name}
        subtitle={`${overview.project.team_name} / ${overview.project.organization_name}`}
      />

      <PanelSection title="Repository mix">
        <SummaryBreakdown summary={overview.summary} />
      </PanelSection>

      <PanelSection title="Recent activity">
        <ActivitySummary snapshot={overview.recent_activity} />
      </PanelSection>

      <PanelSection title="Top suites by case volume">
        {overview.top_suites.length === 0 ? (
          <p className="text-sm text-slate-500">No suites yet.</p>
        ) : (
          <div className="space-y-2">
            {overview.top_suites.map((suite) => (
              <button
                key={suite.id}
                type="button"
                onClick={() => onSelect?.({ type: "suite", id: suite.id })}
                className="flex w-full items-center justify-between rounded-md border border-slate-200 px-3 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-slate-900">{suite.name}</div>
                  <div className="truncate text-xs text-slate-500">
                    {suite.folder_path || "No folder path"}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>{suite.counts.scenario_count ?? 0} scenarios</span>
                  <span>{suite.counts.case_count ?? 0} cases</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Recent runs">
        {overview.recent_runs.length === 0 ? (
          <p className="text-sm text-slate-500">No runs yet.</p>
        ) : (
          <div className="space-y-2">
            {overview.recent_runs.map((run) => (
              <RecentRunItem key={run.id} run={run} />
            ))}
          </div>
        )}
      </PanelSection>
    </>
  );
}
