import { useMemo, useState } from "react";
import { deleteCase, deleteScenario, deleteSection, deleteSuite } from "../../../api/testing";
import type { ProjectTree, TreeCase } from "../../../types/testing";
import CreateNodeModal from "./CreateNodeModal";
import DeleteConfirmModal from "./DeleteConfirmModal";
import SuiteNode from "./SuiteNode";
import { PlusIcon } from "./TreeIcons";
import { filterTreeSuites } from "./utils";
import type { CreateTarget, DeleteTarget, TreeMutationRequest, TreeSelection } from "../../../types/tree";

interface ProjectTreePaneProps {
  tree: ProjectTree;
  selection: TreeSelection | null;
  onSelect: (selection: TreeSelection) => void;
  projectId: string;
  scenarioCasesById: Record<string, TreeCase[]>;
  loadingScenarioIds: Record<string, boolean>;
  onLoadScenarioCases: (scenarioId: string) => Promise<void> | void;
  onOpenCaseEditor: (caseId: string) => void;
  onMutate: (request?: TreeMutationRequest) => Promise<void> | void;
}

export default function ProjectTreePane({
  tree,
  selection,
  onSelect,
  projectId,
  scenarioCasesById,
  loadingScenarioIds,
  onLoadScenarioCases,
  onOpenCaseEditor,
  onMutate,
}: ProjectTreePaneProps) {
  const [search, setSearch] = useState("");
  const [createTarget, setCreateTarget] = useState<CreateTarget>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget>(null);
  const [deleting, setDeleting] = useState(false);

  const filteredSuites = useMemo(() => filterTreeSuites(tree.suites, search), [search, tree.suites]);

  async function handleDeleteConfirm() {
    if (!deleteTarget) {
      return;
    }

    setDeleting(true);
    try {
      if (deleteTarget.type === "suite") {
        await deleteSuite(deleteTarget.suiteId);
        await onMutate({ nextSelection: deleteTarget.nextSelection, resetCaseCache: true });
      } else if (deleteTarget.type === "section") {
        await deleteSection(deleteTarget.suiteId, deleteTarget.sectionId);
        await onMutate({ nextSelection: deleteTarget.nextSelection, resetCaseCache: true });
      } else if (deleteTarget.type === "scenario") {
        await deleteScenario(deleteTarget.sectionId, deleteTarget.scenarioId);
        await onMutate({ nextSelection: deleteTarget.nextSelection, resetCaseCache: true });
      } else {
        await deleteCase(deleteTarget.scenarioId, deleteTarget.caseId);
        await onMutate({
          nextSelection: deleteTarget.nextSelection,
          invalidateScenarioIds: [deleteTarget.scenarioId],
        });
      }
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2.5">
        <div className="relative min-w-0 flex-1">
          <svg
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
            />
          </svg>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search suites, sections, scenarios..."
            className="w-full rounded-md border-0 bg-slate-100 py-1.5 pl-8 pr-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          type="button"
          onClick={() => setCreateTarget({ type: "suite" })}
          title="New test suite"
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500 transition hover:bg-blue-100 hover:text-blue-600"
        >
          <PlusIcon />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {filteredSuites.length === 0 ? (
          <p className="py-6 text-center text-xs text-slate-400">
            {search ? "No results." : "No test suites yet."}
          </p>
        ) : (
          filteredSuites.map((suite) => (
            <SuiteNode
              key={suite.id}
              suite={suite}
              selection={selection}
              scenarioCasesById={scenarioCasesById}
              loadingScenarioIds={loadingScenarioIds}
              onSelect={onSelect}
              onLoadScenarioCases={onLoadScenarioCases}
              onMutate={onMutate}
              onOpenCaseEditor={onOpenCaseEditor}
              onRequestCreate={setCreateTarget}
              onRequestDelete={setDeleteTarget}
            />
          ))
        )}
      </div>

      <CreateNodeModal
        target={createTarget}
        projectId={projectId}
        onClose={() => setCreateTarget(null)}
        onCreated={onMutate}
      />

      <DeleteConfirmModal
        target={deleteTarget}
        loading={deleting}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDeleteConfirm()}
      />
    </div>
  );
}
