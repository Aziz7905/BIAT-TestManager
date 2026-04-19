import { useEffect, useState } from "react";
import { updateSuite } from "../../../api/testing";
import NodeActionMenu from "./NodeActionMenu";
import RenameInlineInput from "./RenameInlineInput";
import SectionNode from "./SectionNode";
import SuiteEditModal from "./SuiteEditModal";
import {
  ChevronIcon,
  CountChip,
  PencilIcon,
  PlusIcon,
  SuiteIcon,
  TrashIcon,
} from "./TreeIcons";
import { buildSuiteDeleteImpact, selectionBelongsToSuite } from "./utils";
import type { DeleteTarget, SuiteNodeProps } from "../../../types/tree";

export default function SuiteNode({
  suite,
  selection,
  scenarioCasesById,
  loadingScenarioIds,
  onSelect,
  onLoadScenarioCases,
  onMutate,
  onOpenCaseEditor,
  onRequestCreate,
  onRequestDelete,
}: SuiteNodeProps) {
  const [open, setOpen] = useState(true);
  const [renaming, setRenaming] = useState(false);
  const [editing, setEditing] = useState(false);
  const active = selection?.type === "suite" && selection.id === suite.id;

  useEffect(() => {
    if (selectionBelongsToSuite(selection, suite)) {
      setOpen(true);
    }
  }, [selection, suite]);

  async function handleRename(nextName: string) {
    setRenaming(false);
    await updateSuite(suite.id, { name: nextName });
    await onMutate({ resetCaseCache: true });
  }

  function buildDeleteTarget(): Exclude<DeleteTarget, null> {
    return {
      type: "suite",
      suiteId: suite.id,
      name: suite.name,
      impact: buildSuiteDeleteImpact(suite),
      nextSelection: selectionBelongsToSuite(selection, suite) ? null : selection,
    };
  }

  return (
    <div className="mb-0.5">
      <div
        className={`group flex items-center gap-1.5 rounded px-2 py-1.5 transition ${
          active ? "bg-blue-50" : "hover:bg-slate-100"
        }`}
      >
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="flex shrink-0 items-center"
        >
          <ChevronIcon open={open} />
        </button>

        <button
          type="button"
          onClick={() => onSelect({ type: "suite", id: suite.id })}
          className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden text-left"
        >
          <SuiteIcon />
          {renaming ? (
            <RenameInlineInput
              value={suite.name}
              onCommit={(value) => void handleRename(value)}
              onCancel={() => setRenaming(false)}
            />
          ) : (
            <span
              className={`min-w-0 flex-1 truncate text-xs font-semibold ${
                active ? "text-blue-700" : "text-slate-800"
              }`}
            >
              {suite.name}
            </span>
          )}
        </button>

        {!renaming && (
          <div className="flex shrink-0 items-center gap-1">
            <CountChip value={suite.counts.case_count ?? 0} />
            <button
              type="button"
              title="Add section"
              onClick={(event) => {
                event.stopPropagation();
                onRequestCreate({
                  type: "section",
                  suiteId: suite.id,
                  suiteName: suite.name,
                });
              }}
              className="rounded-md p-1 text-slate-400 opacity-0 transition group-hover:opacity-100 hover:bg-blue-50 hover:text-blue-600"
            >
              <PlusIcon />
            </button>
            <div className="opacity-0 transition-opacity group-hover:opacity-100">
              <NodeActionMenu
                title="Suite actions"
                items={[
                  {
                    label: "Rename suite",
                    icon: <PencilIcon />,
                    onSelect: () => setRenaming(true),
                  },
                  {
                    label: "Edit details",
                    icon: <PencilIcon />,
                    onSelect: () => setEditing(true),
                  },
                  {
                    label: "Delete suite",
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

      {open && (
        <div className="ml-1">
          {suite.sections.map((section) => (
            <SectionNode
              key={section.id}
              section={section}
              suiteId={suite.id}
              suiteName={suite.name}
              depth={1}
              selection={selection}
              scenarioCasesById={scenarioCasesById}
              loadingScenarioIds={loadingScenarioIds}
              onSelect={onSelect}
              onLoadScenarioCases={onLoadScenarioCases}
              onMutate={onMutate}
              onOpenCaseEditor={onOpenCaseEditor}
              onRequestCreate={onRequestCreate}
              onRequestDelete={onRequestDelete}
            />
          ))}
          {suite.sections.length === 0 && <p className="py-1 pl-7 text-[11px] text-slate-400">No sections.</p>}
        </div>
      )}

      <SuiteEditModal
        open={editing}
        suiteId={editing ? suite.id : null}
        onClose={() => setEditing(false)}
        onSaved={() => void onMutate({ resetCaseCache: true })}
      />
    </div>
  );
}
