import { useState } from "react";
import type {
  ActiveDraftNode,
  DraftEditableField,
  DraftStepEditableField,
} from "../testPilot.types";
import {
  CloseIcon,
  PlusIcon,
  TrashIcon,
} from "../icons/TestPilotIcons";

export default function DraftDetailDrawer({
  node,
  readOnly,
  canGoNext,
  canGoPrevious,
  positionLabel,
  onClose,
  onFieldChange,
  onNext,
  onPrevious,
  onAddStep,
  onDeleteStep,
  onStepChange,
  onTestDataChange,
}: Readonly<{
  node: ActiveDraftNode | null;
  readOnly: boolean;
  canGoNext: boolean;
  canGoPrevious: boolean;
  positionLabel: string;
  onClose: () => void;
  onFieldChange: (field: DraftEditableField, value: string) => void;
  onNext: () => void;
  onPrevious: () => void;
  onAddStep: (afterStepIndex: number) => void;
  onDeleteStep: (stepIndex: number) => void;
  onStepChange: (stepIndex: number, field: DraftStepEditableField, value: string) => void;
  onTestDataChange: (value: Record<string, unknown>) => void;
}>) {
  if (!node) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/45">
      <aside className="ml-auto flex h-full w-full max-w-[min(920px,calc(100vw-32px))] flex-col bg-white shadow-2xl">
        <header className="shrink-0 border-b border-slate-200 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="truncate text-2xl font-semibold text-slate-950">{node.title}</h2>
              <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-600">
                <button type="button" className="font-semibold text-slate-800">High</button>
                <span className="text-slate-300">|</span>
                <span>Functional</span>
                <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                  AI Generated
                </span>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-5">
              <button type="button" onClick={onClose} className="text-sm font-semibold text-slate-900">Save</button>
              <button
                type="button"
                onClick={onClose}
                className="text-slate-400 hover:text-slate-700"
                aria-label="Close details"
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>
          </div>
          <div className="mt-6 flex gap-6 border-b border-slate-200 text-sm font-semibold text-slate-600">
            <button type="button" className="-mb-px border-b-2 border-slate-900 px-1 pb-3 text-slate-950">
              Test details
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {node.type !== "case" && (
            <EditableDetailBlock
              label="Description"
              readOnly={readOnly}
              value={node.description}
              onChange={(value) => onFieldChange("description", value)}
            />
          )}
          {node.preconditions !== undefined && (
            <EditableDetailBlock
              label="Pre-conditions"
              readOnly={readOnly}
              value={node.preconditions}
              onChange={(value) => onFieldChange("preconditions", value)}
            />
          )}
          {node.expectedResult !== undefined && (
            <EditableDetailBlock
              label="Expected result"
              readOnly={readOnly}
              value={node.expectedResult}
              onChange={(value) => onFieldChange("expectedResult", value)}
            />
          )}

          {node.steps?.length ? (
            <div className="mt-7 border-t border-slate-200 pt-5">
              <h3 className="text-sm font-semibold text-slate-800">Test Steps</h3>
              <div className="mt-4 space-y-4">
                {node.steps.map((step) => (
                  <div key={step.step_index} className="grid gap-4 md:grid-cols-[40px_minmax(0,1fr)_minmax(0,1fr)_52px]">
                    <div className="flex flex-col items-center gap-2 text-xs text-slate-500">
                      <span>{step.step_index}</span>
                      <span className="h-4 w-4 rounded-full border-4 border-slate-700 bg-white" />
                      <span className="h-full w-px bg-slate-200" />
                    </div>
                    <EditableStepCard
                      label="Step"
                      value={step.action}
                      readOnly={readOnly}
                      onChange={(value) => onStepChange(step.step_index, "action", value)}
                    />
                    <EditableStepCard
                      label="Outcome"
                      value={step.expected_outcome}
                      readOnly={readOnly}
                      onChange={(value) => onStepChange(step.step_index, "expected_outcome", value)}
                    />
                    <div className="flex flex-col overflow-hidden rounded-md border border-slate-200">
                      <button
                        type="button"
                        disabled={readOnly}
                        onClick={() => onAddStep(step.step_index)}
                        className="flex h-1/2 items-center justify-center text-slate-500 hover:bg-slate-50 disabled:opacity-40"
                        aria-label={`Add a step after step ${step.step_index}`}
                      >
                        <PlusIcon className="h-5 w-5" />
                      </button>
                      <button
                        type="button"
                        disabled={readOnly}
                        onClick={() => onDeleteStep(step.step_index)}
                        className="flex h-1/2 items-center justify-center border-t border-slate-200 text-slate-400 hover:bg-slate-50 disabled:opacity-40"
                        aria-label={`Delete step ${step.step_index}`}
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {node.type === "case" && (
            <div className="mt-7 border-t border-slate-200 pt-5">
              <h3 className="text-sm font-semibold text-slate-800">Test data</h3>
              <EditableJsonBlock
                key={node.id}
                readOnly={readOnly}
                value={node.testData ?? {}}
                onChange={onTestDataChange}
              />
            </div>
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
          <span className="text-sm text-slate-600">{positionLabel}</span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!canGoPrevious}
              onClick={onPrevious}
              className="rounded-md border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 disabled:text-slate-300"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={!canGoNext}
              onClick={onNext}
              className="rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400"
            >
              Next
            </button>
          </div>
        </footer>
      </aside>
    </div>
  );
}

function EditableDetailBlock({
  label,
  readOnly,
  value,
  onChange,
}: Readonly<{ label: string; readOnly: boolean; value: string; onChange: (value: string) => void }>) {
  return (
    <section className="mb-7">
      <h3 className="text-sm font-semibold text-slate-800">{label}</h3>
      <textarea
        value={value}
        disabled={readOnly}
        rows={Math.max(3, Math.min(8, value.split("\n").length + 1))}
        onChange={(event) => onChange(event.target.value)}
        className="mt-3 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-800 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
      />
    </section>
  );
}

function EditableJsonBlock({
  readOnly,
  value,
  onChange,
}: Readonly<{ readOnly: boolean; value: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }>) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState("");

  function commitJson() {
    try {
      const parsed = JSON.parse(text || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setError("Test data must be a JSON object.");
        return;
      }
      setError("");
      onChange(parsed as Record<string, unknown>);
    } catch {
      setError("Invalid JSON. Fix it before saving this draft.");
    }
  }

  return (
    <div className="mt-3">
      <textarea
        value={text}
        disabled={readOnly}
        rows={8}
        onBlur={commitJson}
        onChange={(event) => setText(event.target.value)}
        className="w-full resize-y rounded-md border border-slate-200 bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:opacity-70"
      />
      {error && <p className="mt-2 text-xs font-medium text-red-600">{error}</p>}
    </div>
  );
}

function EditableStepCard({
  label,
  readOnly,
  value,
  onChange,
}: Readonly<{ label: string; readOnly: boolean; value: string; onChange: (value: string) => void }>) {
  return (
    <label className="block rounded-md border border-slate-300 bg-white px-4 py-3">
      <span className="text-sm font-semibold text-slate-500">{label}</span>
      <textarea
        value={value}
        disabled={readOnly}
        rows={3}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full resize-y border-0 p-0 text-sm leading-6 text-slate-800 outline-none disabled:bg-white"
      />
    </label>
  );
}

