import { useEffect, useState } from "react";
import { updateSection } from "../../../api/testing";
import NodeActionMenu from "./NodeActionMenu";
import RenameInlineInput from "./RenameInlineInput";
import ScenarioNode from "./ScenarioNode";
import { ChevronIcon, CountChip, PencilIcon, SectionIcon, TrashIcon } from "./TreeIcons";
import { buildSectionDeleteImpact, selectionBelongsToSection } from "./utils";
import type { DeleteTarget, SectionNodeProps } from "../../../types/tree";

export default function SectionNode({
  section,
  suiteId,
  suiteName,
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
}: SectionNodeProps) {
  const [open, setOpen] = useState(true);
  const [renaming, setRenaming] = useState(false);
  const active = selection?.type === "section" && selection.id === section.id;
  const hasChildren = section.children.length > 0 || section.scenarios.length > 0;

  useEffect(() => {
    if (selectionBelongsToSection(selection, section)) {
      setOpen(true);
    }
  }, [section, selection]);

  async function handleRename(nextName: string) {
    setRenaming(false);
    await updateSection(suiteId, section.id, { name: nextName });
    await onMutate({ resetCaseCache: true });
  }

  function buildDeleteTarget(): Exclude<DeleteTarget, null> {
    return {
      type: "section",
      suiteId,
      sectionId: section.id,
      name: section.name,
      impact: buildSectionDeleteImpact(section),
      nextSelection: selectionBelongsToSection(selection, section)
        ? section.parent_id
          ? { type: "section", id: section.parent_id, parentId: suiteId }
          : { type: "suite", id: suiteId }
        : selection,
    };
  }

  return (
    <>
      <div
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
        className={`group flex items-center gap-1.5 rounded py-1 pr-2 transition ${
          active ? "bg-slate-100" : "hover:bg-slate-100"
        }`}
      >
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            if (hasChildren) {
              setOpen((current) => !current);
            }
          }}
          className="flex shrink-0 items-center"
        >
          {hasChildren ? <ChevronIcon open={open} /> : <span className="h-3 w-3 shrink-0" />}
        </button>

        <button
          type="button"
          onClick={() => onSelect({ type: "section", id: section.id, parentId: suiteId })}
          className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden text-left"
        >
          <SectionIcon />
          {renaming ? (
            <RenameInlineInput
              value={section.name}
              onCommit={(value) => void handleRename(value)}
              onCancel={() => setRenaming(false)}
            />
          ) : (
            <span
              className={`min-w-0 flex-1 truncate text-xs font-medium ${
                active ? "text-slate-900" : "text-slate-600"
              }`}
            >
              {section.name}
            </span>
          )}
        </button>

        {!renaming && (
          <div className="flex shrink-0 items-center gap-1">
            <CountChip value={section.counts.scenario_count ?? section.counts.case_count ?? 0} />
            <div className="opacity-0 transition-opacity group-hover:opacity-100">
              <NodeActionMenu
                title="Add section content"
                variant="plus"
                items={[
                  {
                    label: "Child section",
                    onSelect: () =>
                      onRequestCreate({
                        type: "section",
                        suiteId,
                        suiteName,
                        parentId: section.id,
                        parentName: section.name,
                      }),
                  },
                  {
                    label: "Scenario",
                    onSelect: () =>
                      onRequestCreate({
                        type: "scenario",
                        sectionId: section.id,
                        sectionName: section.name,
                      }),
                  },
                ]}
              />
            </div>
            <div className="opacity-0 transition-opacity group-hover:opacity-100">
              <NodeActionMenu
                title="Section actions"
                items={[
                  {
                    label: "Rename section",
                    icon: <PencilIcon />,
                    onSelect: () => setRenaming(true),
                  },
                  {
                    label: "Delete section",
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
        <div>
          {section.children.map((child) => (
            <SectionNode
              key={child.id}
              section={child}
              suiteId={suiteId}
              suiteName={suiteName}
              depth={depth + 1}
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
          {section.scenarios.map((scenario) => (
            <ScenarioNode
              key={scenario.id}
              scenario={scenario}
              sectionId={section.id}
              depth={depth + 1}
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
        </div>
      )}
    </>
  );
}
