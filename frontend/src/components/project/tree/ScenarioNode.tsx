import { useEffect, useState } from "react";
import { cloneScenario, updateScenario } from "../../../api/testing";
import type { TreeScenario } from "../../../types/testing";
import CaseNode from "./CaseNode";
import NodeActionMenu from "./NodeActionMenu";
import RenameInlineInput from "./RenameInlineInput";
import ScenarioEditModal from "./ScenarioEditModal";
import {
  ChevronIcon,
  CountChip,
  DuplicateIcon,
  Dot,
  PencilIcon,
  ScenarioIcon,
  TrashIcon,
} from "./TreeIcons";
import { buildScenarioDeleteImpact, priorityTone } from "./utils";
import type {
  DeleteTarget,
  RepositoryTreeNodeProps,
  ScenarioCasesState,
  TreeSelection,
} from "../../../types/tree";

interface ScenarioNodeProps
  extends Pick<
      RepositoryTreeNodeProps,
      "onMutate" | "onOpenCaseEditor" | "onRequestCreate" | "onRequestDelete"
    >,
    ScenarioCasesState {
  scenario: TreeScenario;
  sectionId: string;
  depth: number;
  selection: TreeSelection | null;
  onSelect: (selection: TreeSelection) => void;
}

export default function ScenarioNode({
  scenario,
  sectionId,
  depth,
  selection,
  scenarioCasesById,
  loadingScenarioIds,
  onSelect,
  onLoadScenarioCases,
  onMutate,
  onOpenCaseEditor,
  onRequestCreate,
  onRequestDelete,
}: ScenarioNodeProps) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [editing, setEditing] = useState(false);
  const active = selection?.type === "scenario" && selection.id === scenario.id;
  const hasCases = scenario.case_count > 0;
  const cases = scenarioCasesById[scenario.id] ?? [];
  const isLoadingCases = Boolean(loadingScenarioIds[scenario.id]);

  useEffect(() => {
    if (selection?.type === "case" && selection.parentId === scenario.id) {
      setOpen(true);
      void onLoadScenarioCases(scenario.id);
    }
  }, [onLoadScenarioCases, scenario.id, selection]);

  async function handleRename(nextTitle: string) {
    setRenaming(false);
    await updateScenario(sectionId, scenario.id, { title: nextTitle });
    await onMutate({ resetCaseCache: true });
  }

  async function handleDuplicate() {
    const cloned = await cloneScenario(scenario.id);
    await onMutate({
      nextSelection: {
        type: "scenario",
        id: cloned.id,
        parentId: cloned.section_id ?? sectionId,
      },
      resetCaseCache: true,
    });
  }

  function buildDeleteTarget(): Exclude<DeleteTarget, null> {
    const affectsSelection =
      (selection?.type === "scenario" && selection.id === scenario.id) ||
      (selection?.type === "case" && selection.parentId === scenario.id);

    return {
      type: "scenario",
      sectionId,
      scenarioId: scenario.id,
      name: scenario.title,
      impact: buildScenarioDeleteImpact(scenario.case_count),
      nextSelection: affectsSelection ? { type: "section", id: sectionId } : selection,
    };
  }

  async function handleToggleOpen() {
    if (!hasCases) {
      return;
    }

    const nextOpen = !open;
    setOpen(nextOpen);
    if (nextOpen) {
      await onLoadScenarioCases(scenario.id);
    }
  }

  async function handleSelectScenario() {
    onSelect({ type: "scenario", id: scenario.id, parentId: sectionId });
    if (hasCases) {
      setOpen(true);
      await onLoadScenarioCases(scenario.id);
    }
  }

  return (
    <>
      <div
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
        className={`group flex items-center gap-1.5 rounded py-1.5 pr-2 transition ${
          active ? "bg-blue-50" : "hover:bg-slate-100"
        }`}
      >
        <button type="button" onClick={() => void handleToggleOpen()} className="flex shrink-0 items-center">
          {hasCases ? <ChevronIcon open={open} /> : <span className="h-3 w-3 shrink-0" />}
        </button>

        <button
          type="button"
          onClick={() => void handleSelectScenario()}
          className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden text-left"
        >
          <ScenarioIcon />
          {renaming ? (
            <RenameInlineInput
              value={scenario.title}
              onCommit={(value) => void handleRename(value)}
              onCancel={() => setRenaming(false)}
            />
          ) : (
            <span
              className={`truncate text-xs font-medium ${
                active ? "text-blue-700" : "text-slate-700 hover:text-slate-900"
              }`}
            >
              {scenario.title}
            </span>
          )}
        </button>

        {!renaming && (
          <div className="flex shrink-0 items-center gap-1">
            <Dot tone={priorityTone(scenario.priority)} />
            <CountChip value={scenario.case_count} />
            <button
              type="button"
              title="Add test case"
              onClick={(event) => {
                event.stopPropagation();
                onRequestCreate({
                  type: "case",
                  scenarioId: scenario.id,
                  scenarioTitle: scenario.title,
                });
              }}
              className="rounded-md p-1 text-slate-400 opacity-0 transition group-hover:opacity-100 hover:bg-blue-50 hover:text-blue-600"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <div className="opacity-0 transition-opacity group-hover:opacity-100">
              <NodeActionMenu
                title="Scenario actions"
                items={[
                  {
                    label: "Rename scenario",
                    icon: <PencilIcon />,
                    onSelect: () => setRenaming(true),
                  },
                  {
                    label: "Edit details",
                    icon: <PencilIcon />,
                    onSelect: () => setEditing(true),
                  },
                  {
                    label: "Duplicate scenario",
                    icon: <DuplicateIcon />,
                    onSelect: () => void handleDuplicate(),
                  },
                  {
                    label: "Delete scenario",
                    icon: <TrashIcon />,
                    tone: "danger",
                    onSelect: () => onRequestDelete(buildDeleteTarget()),
                  },
                ]}
              />
            </div>
          </div>
        )}
      </div>

      {open && hasCases && (
        <div>
          {isLoadingCases && (
            <p
              style={{ paddingLeft: `${(depth + 1) * 12 + 14}px` }}
              className="py-1 text-[11px] text-slate-400"
            >
              Loading cases...
            </p>
          )}
          {!isLoadingCases && cases.length === 0 && (
            <p
              style={{ paddingLeft: `${(depth + 1) * 12 + 14}px` }}
              className="py-1 text-[11px] text-slate-400"
            >
              No cases yet.
            </p>
          )}
          {cases.map((testCase) => (
            <CaseNode
              key={testCase.id}
              testCase={testCase}
              scenarioId={scenario.id}
              depth={depth + 1}
              selection={selection}
              onSelect={onSelect}
              onMutate={onMutate}
              onOpenCaseEditor={onOpenCaseEditor}
              onRequestDelete={onRequestDelete}
            />
          ))}
        </div>
      )}

      <ScenarioEditModal
        open={editing}
        scenarioId={editing ? scenario.id : null}
        sectionId={editing ? sectionId : null}
        onClose={() => setEditing(false)}
        onSaved={() => void onMutate({ resetCaseCache: true })}
      />
    </>
  );
}
