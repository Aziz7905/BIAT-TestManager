import { useEffect, useState } from "react";
import { Button, Modal } from "../../ui";
import { createSpecificationSource } from "../../../api/specs";
import type {
  CreateSpecificationSourcePayload,
  SpecificationSourceDetail,
} from "../../../types/specs";

interface CreateSpecificationSourceModalProps {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onCreated: (source: SpecificationSourceDetail) => void;
}

type SourceInputMode = "file" | "jira" | "text";

function createInitialForm(projectId: string): CreateSpecificationSourcePayload {
  return {
    project: projectId,
    name: "",
    raw_text: "",
    jira_issue_key: "",
    file: null,
    auto_parse: true,
    auto_import: false,
  };
}

export default function CreateSpecificationSourceModal({
  open,
  projectId,
  onClose,
  onCreated,
}: CreateSpecificationSourceModalProps) {
  const [form, setForm] = useState<CreateSpecificationSourcePayload>(() =>
    createInitialForm(projectId)
  );
  const [mode, setMode] = useState<SourceInputMode>("file");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(createInitialForm(projectId));
      setMode("file");
      setError(null);
    }
  }, [open, projectId]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (mode === "file" && !form.file) {
      setError("Choose a requirement file first.");
      return;
    }
    if (mode === "jira" && !form.jira_issue_key?.trim()) {
      setError("Enter a Jira issue key.");
      return;
    }
    if (mode === "text" && !form.raw_text?.trim()) {
      setError("Paste requirement text first.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const source = await createSpecificationSource(buildPayloadForMode(form, mode));
      onCreated(source);
    } catch {
      setError("Could not create this source.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New specification source"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form="create-specification-source-form" type="submit" isLoading={saving}>
            Create
          </Button>
        </>
      }
    >
      <form id="create-specification-source-form" onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Name</label>
          <input
            value={form.name ?? ""}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            placeholder="Optional source name"
            className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
          <p className="text-xs text-slate-500">
            BIAT detects PDF, DOCX, XLSX, CSV, Jira, or pasted text automatically.
          </p>
        </div>

        <div className="grid gap-2 md:grid-cols-3">
          {[
            { value: "file" as const, label: "Upload file", description: "PDF, DOCX, XLSX, CSV" },
            { value: "jira" as const, label: "Jira issue", description: "Import by issue key" },
            { value: "text" as const, label: "Paste text", description: "Quick requirement input" },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setMode(option.value)}
              className={[
                "rounded-xl border px-3.5 py-3 text-left transition",
                mode === option.value
                  ? "border-slate-900 bg-slate-900 text-white shadow-sm"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50",
              ].join(" ")}
            >
              <span className="block text-sm font-semibold">{option.label}</span>
              <span
                className={[
                  "mt-1 block text-xs",
                  mode === option.value ? "text-slate-200" : "text-slate-500",
                ].join(" ")}
              >
                {option.description}
              </span>
            </button>
          ))}
        </div>

        {mode === "file" && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Requirement file</label>
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,.csv,.txt"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  file: event.target.files?.[0] ?? null,
                }))
              }
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-medium"
            />
          </div>
        )}

        {mode === "jira" && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Jira issue key</label>
            <input
              value={form.jira_issue_key ?? ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, jira_issue_key: event.target.value }))
              }
              placeholder="REQ-421"
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        )}

        {mode === "text" && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Text content</label>
            <textarea
              rows={10}
              value={form.raw_text ?? ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, raw_text: event.target.value }))
              }
              placeholder="Paste the requirement, acceptance criteria, or workflow notes here."
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}

function buildPayloadForMode(
  form: CreateSpecificationSourcePayload,
  mode: SourceInputMode
): CreateSpecificationSourcePayload {
  const base = {
    project: form.project,
    name: form.name,
    auto_parse: form.auto_parse,
    auto_import: form.auto_import,
  };

  if (mode === "file") {
    return { ...base, file: form.file ?? null };
  }
  if (mode === "jira") {
    return { ...base, jira_issue_key: form.jira_issue_key?.trim() ?? "" };
  }
  return { ...base, raw_text: form.raw_text?.trim() ?? "" };
}
