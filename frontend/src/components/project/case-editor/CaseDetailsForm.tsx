import type { EditableCaseDraft } from "../../../types/case-editor";

interface CaseDetailsFormProps {
  draft: EditableCaseDraft;
  testDataError: string | null;
  onFieldChange: <K extends keyof EditableCaseDraft>(field: K, value: EditableCaseDraft[K]) => void;
}

export default function CaseDetailsForm({
  draft,
  testDataError,
  onFieldChange,
}: CaseDetailsFormProps) {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            aria-label="Title"
            value={draft.title}
            onChange={(event) => onFieldChange("title", event.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Expected result <span className="text-red-500">*</span>
          </label>
          <textarea
            aria-label="Expected result"
            rows={4}
            value={draft.expected_result}
            onChange={(event) => onFieldChange("expected_result", event.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Preconditions</label>
          <textarea
            aria-label="Preconditions"
            rows={4}
            value={draft.preconditions}
            onChange={(event) => onFieldChange("preconditions", event.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Test data (JSON)</label>
          <textarea
            aria-label="Test data"
            rows={6}
            value={draft.test_data_input}
            onChange={(event) => onFieldChange("test_data_input", event.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
          {testDataError && <p className="mt-1 text-xs text-red-600">{testDataError}</p>}
        </div>
      </div>

      <aside className="space-y-4">
        <div className="rounded-md border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-900">Execution settings</h3>
          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Design status
              </label>
              <select
                aria-label="Design status"
                value={draft.design_status}
                onChange={(event) => onFieldChange("design_status", event.target.value as EditableCaseDraft["design_status"])}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                <option value="draft">Draft</option>
                <option value="in_review">In review</option>
                <option value="approved">Approved</option>
                <option value="archived">Archived</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Automation status
              </label>
              <select
                aria-label="Automation status"
                value={draft.automation_status}
                onChange={(event) =>
                  onFieldChange(
                    "automation_status",
                    event.target.value as EditableCaseDraft["automation_status"]
                  )
                }
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                <option value="manual">Manual</option>
                <option value="automated">Automated</option>
                <option value="in_progress">In progress</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                On failure
              </label>
              <select
                aria-label="On failure"
                value={draft.on_failure}
                onChange={(event) => onFieldChange("on_failure", event.target.value as EditableCaseDraft["on_failure"])}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                <option value="fail_but_continue">Fail but continue</option>
                <option value="fail_and_stop">Fail and stop</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Timeout (ms)
              </label>
              <input
                aria-label="Timeout (ms)"
                type="number"
                min={0}
                value={draft.timeout_ms}
                onChange={(event) => onFieldChange("timeout_ms", event.target.value)}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
            </div>
          </div>
        </div>

        <div className="rounded-md border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-900">Linked specifications</h3>
          {draft.linked_specifications.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">No linked specifications yet.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {draft.linked_specifications.map((specification) => (
                <div key={specification.id} className="rounded-md border border-slate-200 px-3 py-2">
                  <div className="text-sm font-medium text-slate-900">{specification.title}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {specification.external_reference || specification.source_type}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
