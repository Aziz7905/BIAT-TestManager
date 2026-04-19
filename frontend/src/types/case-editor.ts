import type { AutomationStatus, DesignStatus, LinkedSpec, OnFailureBehavior } from "./testing";

export interface EditableStepRow {
  id: string;
  step: string;
  outcome: string;
}

export interface EditableCaseDraft {
  title: string;
  preconditions: string;
  expected_result: string;
  design_status: DesignStatus;
  automation_status: AutomationStatus;
  on_failure: OnFailureBehavior;
  timeout_ms: string;
  test_data_input: string;
  steps: EditableStepRow[];
  linked_specifications: LinkedSpec[];
}
