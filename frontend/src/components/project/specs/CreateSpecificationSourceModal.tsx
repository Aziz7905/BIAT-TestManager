import { useEffect, useMemo, useState } from "react";
import { Button, Modal } from "../../ui";
import { createSpecificationSource } from "../../../api/specs";
import type {
  CreateSpecificationSourcePayload,
  SpecificationSourceDetail,
  SpecificationSourceType,
} from "../../../types/specs";
import { sourceTypeLabel } from "./shared";

interface CreateSpecificationSourceModalProps {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onCreated: (source: SpecificationSourceDetail) => void;
}

const SOURCE_TYPE_OPTIONS: SpecificationSourceType[] = [
  "plain_text",
  "url",
  "jira_issue",
  "pdf",
  "docx",
  "xlsx",
  "csv",
  "file_upload",
];

function createInitialForm(projectId: string): CreateSpecificationSourcePayload {
  return {
    project: projectId,
    name: "",
    source_type: "plain_text",
    raw_text: "",
    source_url: "",
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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(createInitialForm(projectId));
      setError(null);
    }
  }, [open, projectId]);

  const needsFile = useMemo(
    () => ["pdf", "docx", "xlsx", "csv", "file_upload"].includes(form.source_type),
    [form.source_type]
  );

  const needsText = form.source_type === "plain_text" || form.source_type === "manual";
  const needsUrl = form.source_type === "url";
  const needsJira = form.source_type === "jira_issue";

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const source = await createSpecificationSource(form);
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
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Name</label>
            <input
              value={form.name ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Optional source name"
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Source type</label>
            <select
              value={form.source_type}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  source_type: event.target.value as SpecificationSourceType,
                  file: null,
                }))
              }
              className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              {SOURCE_TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {sourceTypeLabel(option)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {needsFile && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">File</label>
            <input
              type="file"
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

        {needsText && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Text content</label>
            <textarea
              rows={10}
              value={form.raw_text ?? ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, raw_text: event.target.value }))
              }
              placeholder="Paste the requirement text here."
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        )}

        {needsUrl && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Source URL</label>
            <input
              value={form.source_url ?? ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, source_url: event.target.value }))
              }
              placeholder="https://..."
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        )}

        {needsJira && (
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

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}
