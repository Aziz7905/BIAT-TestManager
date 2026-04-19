import type { ProjectTree, TreeCase, TreeSection, TreeSuite } from "./testing";

export type SelectionType = "suite" | "section" | "scenario" | "case";

export interface TreeSelection {
  type: SelectionType;
  id: string;
  parentId?: string;
}

export interface TreeMutationRequest {
  nextSelection?: TreeSelection | null;
  resetCaseCache?: boolean;
  invalidateScenarioIds?: string[];
}

export type CreateTarget =
  | { type: "suite" }
  | { type: "section"; suiteId: string; suiteName: string; parentId?: string; parentName?: string }
  | { type: "scenario"; sectionId: string; sectionName: string }
  | { type: "case"; scenarioId: string; scenarioTitle: string }
  | null;

export interface DeleteImpactSummary {
  sectionCount?: number;
  childSectionCount?: number;
  scenarioCount?: number;
  caseCount?: number;
}

export type DeleteTarget =
  | {
      type: "suite";
      suiteId: string;
      name: string;
      impact: DeleteImpactSummary;
      nextSelection: TreeSelection | null;
    }
  | {
      type: "section";
      suiteId: string;
      sectionId: string;
      name: string;
      impact: DeleteImpactSummary;
      nextSelection: TreeSelection | null;
    }
  | {
      type: "scenario";
      sectionId: string;
      scenarioId: string;
      name: string;
      impact: DeleteImpactSummary;
      nextSelection: TreeSelection | null;
    }
  | {
      type: "case";
      scenarioId: string;
      caseId: string;
      name: string;
      impact: DeleteImpactSummary;
      nextSelection: TreeSelection | null;
    }
  | null;

export interface RepositoryTreeNodeProps {
  selection: TreeSelection | null;
  onSelect: (selection: TreeSelection) => void;
  onRequestCreate: (target: CreateTarget) => void;
  onRequestDelete: (target: Exclude<DeleteTarget, null>) => void;
  onMutate: (request?: TreeMutationRequest) => Promise<void> | void;
  onOpenCaseEditor: (caseId: string) => void;
}

export interface ScenarioCasesState {
  scenarioCasesById: Record<string, TreeCase[]>;
  loadingScenarioIds: Record<string, boolean>;
  onLoadScenarioCases: (scenarioId: string) => Promise<void> | void;
}

export interface SuiteNodeProps extends RepositoryTreeNodeProps, ScenarioCasesState {
  suite: TreeSuite;
}

export interface SectionNodeProps extends RepositoryTreeNodeProps, ScenarioCasesState {
  section: TreeSection;
  suiteId: string;
  suiteName: string;
  depth: number;
}

export function selectionExistsInTree(tree: ProjectTree, selection: TreeSelection | null) {
  if (!selection) return true;
  if (selection.type === "suite") {
    return tree.suites.some((suite) => suite.id === selection.id);
  }
  return tree.suites.some((suite) => selectionExistsInSuite(suite, selection));
}

function selectionExistsInSuite(suite: TreeSuite, selection: TreeSelection): boolean {
  if (selection.type === "suite") return selection.id === suite.id;
  return suite.sections.some((section) => selectionExistsInSection(section, selection));
}

function selectionExistsInSection(section: TreeSection, selection: TreeSelection): boolean {
  if (selection.type === "section" && selection.id === section.id) return true;
  if (selection.type === "scenario" && section.scenarios.some((s) => s.id === selection.id)) return true;
  if (
    selection.type === "case" &&
    selection.parentId &&
    section.scenarios.some((s) => s.id === selection.parentId)
  ) {
    return true;
  }
  return section.children.some((child) => selectionExistsInSection(child, selection));
}
