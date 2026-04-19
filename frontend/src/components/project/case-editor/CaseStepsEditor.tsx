import { Button } from "../../ui";
import type { EditableStepRow } from "../../../types/case-editor";

interface CaseStepsEditorProps {
  rows: EditableStepRow[];
  onChange: (rows: EditableStepRow[]) => void;
}

function createEmptyRow(): EditableStepRow {
  return {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2),
    step: "",
    outcome: "",
  };
}

export default function CaseStepsEditor({ rows, onChange }: CaseStepsEditorProps) {
  function handleRowChange(id: string, field: "step" | "outcome", value: string) {
    onChange(
      rows.map((row) => (row.id === id ? { ...row, [field]: value } : row))
    );
  }

  function handleDeleteRow(id: string) {
    if (rows.length === 1) {
      onChange([{ ...rows[0], step: "", outcome: "" }]);
      return;
    }
    onChange(rows.filter((row) => row.id !== id));
  }

  function handleAddRow() {
    onChange([...rows, createEmptyRow()]);
  }

  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div
          key={row.id}
          className="grid grid-cols-1 gap-3 rounded-md border border-slate-200 p-3 xl:grid-cols-[48px_minmax(0,1fr)_minmax(0,1fr)_40px]"
        >
          <div className="pt-2 text-sm font-semibold text-slate-400">{index + 1}</div>

          <div className="rounded-md border border-slate-200 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Step</div>
            <textarea
              aria-label={`Step ${index + 1}`}
              rows={5}
              value={row.step}
              onChange={(event) => handleRowChange(row.id, "step", event.target.value)}
              className="w-full resize-none border-0 p-0 text-sm text-slate-700 focus:outline-none"
              placeholder="Describe the user action or navigation."
            />
          </div>

          <div className="rounded-md border border-slate-200 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Outcome
            </div>
            <textarea
              aria-label={`Outcome ${index + 1}`}
              rows={5}
              value={row.outcome}
              onChange={(event) => handleRowChange(row.id, "outcome", event.target.value)}
              className="w-full resize-none border-0 p-0 text-sm text-slate-700 focus:outline-none"
              placeholder="Describe the expected visible result or assertion."
            />
          </div>

          <div className="flex items-start justify-end">
            <button
              type="button"
              aria-label={`Delete step ${index + 1}`}
              onClick={() => handleDeleteRow(row.id)}
              className="rounded-md p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M8 7V5a1 1 0 011-1h6a1 1 0 011 1v2"
                />
              </svg>
            </button>
          </div>
        </div>
      ))}

      <Button variant="secondary" size="sm" onClick={handleAddRow}>
        Add step
      </Button>
    </div>
  );
}

export function createInitialStepRows() {
  return [createEmptyRow()];
}
