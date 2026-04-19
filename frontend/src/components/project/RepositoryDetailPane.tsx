import { useEffect, useState } from "react";
import {
  getCaseWorkspace,
  getProjectRepositoryOverview,
  getScenarioOverview,
  getSectionOverview,
  getSuiteOverview,
} from "../../api/testing";
import type {
  CaseWorkspace,
  ProjectRepositoryOverview,
  ScenarioOverview,
  SectionOverview,
  SuiteOverview,
} from "../../types/testing";
import { EmptyState, Spinner } from "../ui";
import CaseWorkspacePanel from "./repository/CaseWorkspacePanel";
import ProjectOverviewPanel from "./repository/ProjectOverviewPanel";
import ScenarioOverviewPanel from "./repository/ScenarioOverviewPanel";
import SectionOverviewPanel from "./repository/SectionOverviewPanel";
import SuiteOverviewPanel from "./repository/SuiteOverviewPanel";
import type { TreeSelection } from "../../types/tree";

type RepositoryDetailState =
  | { kind: "project"; data: ProjectRepositoryOverview }
  | { kind: "suite"; data: SuiteOverview }
  | { kind: "section"; data: SectionOverview }
  | { kind: "scenario"; data: ScenarioOverview }
  | { kind: "case"; data: CaseWorkspace };

interface RepositoryDetailPaneProps {
  projectId: string;
  selection: TreeSelection | null;
  refreshKey?: number;
  onSelect?: (selection: TreeSelection) => void;
  onEditCase?: (caseId: string) => void;
  onScenarioSaved?: () => void;
}

export default function RepositoryDetailPane({
  projectId,
  selection,
  refreshKey = 0,
  onSelect,
  onEditCase,
  onScenarioSaved,
}: RepositoryDetailPaneProps) {
  const [detail, setDetail] = useState<RepositoryDetailState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const payload = selection
          ? await loadSelectionDetail(selection)
          : ({
              kind: "project",
              data: await getProjectRepositoryOverview(projectId),
            } as RepositoryDetailState);

        if (!cancelled) {
          setDetail(payload);
        }
      } catch {
        if (!cancelled) {
          setDetail(null);
          setError("Failed to load repository details.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    if (projectId) {
      void load();
    }

    return () => {
      cancelled = true;
    };
  }, [projectId, refreshKey, selection]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <EmptyState
          title="Could not load this panel"
          description={error || "Something went wrong while loading repository details."}
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-white">
      {detail.kind === "project" && <ProjectOverviewPanel overview={detail.data} onSelect={onSelect} />}
      {detail.kind === "suite" && <SuiteOverviewPanel overview={detail.data} onSelect={onSelect} />}
      {detail.kind === "section" && <SectionOverviewPanel overview={detail.data} onSelect={onSelect} />}
      {detail.kind === "scenario" && (
        <ScenarioOverviewPanel
          overview={detail.data}
          onSelect={onSelect}
          onEditCase={onEditCase}
          onScenarioSaved={onScenarioSaved}
        />
      )}
      {detail.kind === "case" && <CaseWorkspacePanel testCase={detail.data} onEditCase={onEditCase} />}
    </div>
  );
}

async function loadSelectionDetail(selection: TreeSelection): Promise<RepositoryDetailState> {
  if (selection.type === "suite") {
    return { kind: "suite", data: await getSuiteOverview(selection.id) };
  }
  if (selection.type === "section") {
    return { kind: "section", data: await getSectionOverview(selection.id) };
  }
  if (selection.type === "scenario") {
    return { kind: "scenario", data: await getScenarioOverview(selection.id) };
  }
  return { kind: "case", data: await getCaseWorkspace(selection.id) };
}
