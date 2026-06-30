import type {
  AIGenerationCaseDraft,
  AIGenerationStepDraft,
} from "../../types/ai";

export type SavingState = "draft" | "approved" | null;
export type AttachmentMenu = "closed" | "open";
export type ProjectTargetMode = "auto" | "existing" | "new";
export type ComposerMode = "clarify" | "refine" | "disabled" | "hidden";
export type CaseSelectionFilter = "all" | "selected" | "unselected";
export type ReviewFilterValue = "all" | string;

export interface GenerationEvent {
  type: string;
  message?: string;
  payload?: unknown;
  created_at?: string;
}

export interface LaunchContext {
  projectId: string | null;
  suiteId: string | null;
  sectionId: string | null;
  scenarioId: string | null;
  caseId: string | null;
  selectionType: string | null;
  labels: {
    project?: string;
    suite?: string;
    section?: string;
    scenario?: string;
    case?: string;
  };
}

export interface DraftStats {
  sectionCount: number;
  scenarioCount: number;
  caseCount: number;
}

export interface DraftStructureStats {
  suiteCount: number;
  sectionCount: number;
  childSectionCount: number;
  scenarioCount: number;
  caseCount: number;
}

export interface CoverageStats {
  selectedCases: number;
  totalCases: number;
  positiveScenarios: number;
  negativeScenarios: number;
  exploratoryScenarios: number;
  warningCount: number;
  casesWithData: number;
  stepCount: number;
}

export interface ActiveDraftNode {
  id: string;
  type: "suite" | "section" | "scenario" | "case";
  title: string;
  description: string;
  meta: string[];
  steps?: AIGenerationCaseDraft["steps"];
  preconditions?: string;
  expectedResult?: string;
  testData?: Record<string, unknown>;
}

export type DraftEditableField = "title" | "description" | "preconditions" | "expectedResult";
export type DraftStepEditableField = keyof Pick<AIGenerationStepDraft, "action" | "expected_outcome">;

export interface DraftReference {
  draft_id: string;
  label: string;
  type: "scenario" | "case";
}
