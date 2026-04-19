import { useEffect, useState } from "react";
import { Button, Modal } from "../../ui";
import { updateSpecificationSourceRecord } from "../../../api/specs";
import type {
  SpecificationSourceRecord,
  UpdateSpecificationSourceRecordPayload,
} from "../../../types/specs";

interface SourceRecordEditModalProps {
  open: boolean;
  sourceId: string | null;
  record: SpecificationSourceRecord | null;
  onClose: () => void;
  onSaved: () => void;
}

function createDraft(record: SpecificationSourceRecord | null): UpdateSpecificationSourceRecordPayload {
  return {
    title: record?.title ?? "",
    content: record?.content ?? "",
    is_selected: record?.is_selected ?? true,
    external_reference: record?.external_reference ?? "",
    section_label: record?.section_label ?? "",
  };
}

export default function SourceRecordEditModal({
  open,
  sourceId,
  record,
  onClose,
  onSaved,
}: SourceRecordEditModalProps) {
  const [draft, setDraft] = useState<UpdateSpecificationSourceRecordPayload>(() =>
    createDraft(record)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setDraft(createDraft(record));
      setError(null);
    }
  }, [open, record]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!sourceId || !record) return;
    setSaving(true);
    setError(null);

    try {
      await updateSpecificationSourceRecord(sourceId, record.id, draft);
      onSaved();
    } catch {
      setError("Could not save this source record.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={record ? `Record ${record.record_index + 1}` : "Source record"}
      size="xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form="edit-specification-record-form" type="submit" isLoading={saving}>
            Save
          </Button>
        </>
      }
    >
      {!record ? null : (
        <form id="edit-specification-record-form" onSubmit={handleSubmit} className="space-y-4">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={Boolean(draft.is_selected)}
              onChange={(event) =>
                setDraft((current) => ({ ...current, is_selected: event.target.checked }))
              }
            />
            Selected for import
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700">External reference</label>
              <input
                value={draft.external_reference ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    external_reference: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700">Section label</label>
              <input
                value={draft.section_label ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, section_label: event.target.value }))
                }
                className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Title</label>
            <input
              value={draft.title ?? ""}
              onChange={(event) =>
                setDraft((current) => ({ ...current, title: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Content</label>
            <textarea
              rows={12}
              value={draft.content ?? ""}
              onChange={(event) =>
                setDraft((current) => ({ ...current, content: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>
      )}
    </Modal>
  );
}
