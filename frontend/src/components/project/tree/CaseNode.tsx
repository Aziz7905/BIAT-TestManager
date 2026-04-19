import { cloneCase } from "../../../api/testing";
import type { TreeCase } from "../../../types/testing";
import NodeActionMenu from "./NodeActionMenu";
import { Dot, DuplicateIcon, PencilIcon, TrashIcon } from "./TreeIcons";
import { automationTone, buildCaseDeleteImpact, designStatusTone, resultTone } from "./utils";
import type { RepositoryTreeNodeProps, TreeSelection } from "../../../types/tree";

interface CaseNodeProps extends Pick<RepositoryTreeNodeProps, "onMutate" | "onOpenCaseEditor" | "onRequestDelete"> {
  testCase: TreeCase;
  scenarioId: string;
  depth: number;
  selection: TreeSelection | null;
  onSelect: (selection: TreeSelection) => void;
}

export default function CaseNode({
  testCase,
  scenarioId,
  depth,
  selection,
  onSelect,
  onMutate,
  onOpenCaseEditor,
  onRequestDelete,
}: CaseNodeProps) {
  const active = selection?.type === "case" && selection.id === testCase.id;

  async function handleDuplicate() {
    const cloned = await cloneCase(testCase.id);
    await onMutate({
      nextSelection: { type: "case", id: cloned.id, parentId: scenarioId },
      invalidateScenarioIds: [scenarioId],
    });
  }

  return (
    <div
      style={{ paddingLeft: `${depth * 12 + 14}px` }}
      className={`group flex items-center gap-2 rounded py-1.5 pr-3 text-xs transition ${
        active ? "bg-blue-600 text-white" : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect({ type: "case", id: testCase.id, parentId: scenarioId })}
        className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden text-left"
      >
        <div className="flex shrink-0 items-center gap-1">
          <Dot tone={designStatusTone(testCase.design_status)} />
          <Dot tone={automationTone(testCase.automation_status)} />
          <Dot tone={resultTone(testCase.latest_result_status)} />
        </div>
        <span className="truncate">{testCase.title}</span>
      </button>

      <div className="opacity-0 transition-opacity group-hover:opacity-100">
        <NodeActionMenu
          title="Case actions"
          items={[
            {
              label: "Edit case",
              icon: <PencilIcon />,
              onSelect: () => onOpenCaseEditor(testCase.id),
            },
            {
              label: "Duplicate case",
              icon: <DuplicateIcon />,
              onSelect: () => void handleDuplicate(),
            },
            {
              label: "Delete case",
              icon: <TrashIcon />,
              tone: "danger",
              onSelect: () =>
                onRequestDelete({
                  type: "case",
                  scenarioId,
                  caseId: testCase.id,
                  name: testCase.title,
                  impact: buildCaseDeleteImpact(),
                  nextSelection:
                    selection?.type === "case" && selection.id === testCase.id
                      ? { type: "scenario", id: scenarioId }
                      : selection,
                }),
            },
          ]}
        />
      </div>
    </div>
  );
}
