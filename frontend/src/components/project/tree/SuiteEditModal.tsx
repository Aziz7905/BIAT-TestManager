import { useEffect, useState } from "react";
import { getSuiteOverview, updateSuite } from "../../../api/testing";
import { Button, Modal, Spinner } from "../../ui";

interface SuiteEditModalProps {
  open: boolean;
  suiteId: string | null;
  onClose: () => void;
  onSaved: () => void;
}

export default function SuiteEditModal({ open, suiteId, onClose, onSaved }: SuiteEditModalProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [folderPath, setFolderPath] = useState("");

  useEffect(() => {
    if (!open || !suiteId) return;
    let cancelled = false;
    setLoading(true);
    getSuiteOverview(suiteId)
      .then((suite) => {
        if (cancelled) return;
        setName(suite.name);
        setDescription(suite.description ?? "");
        setFolderPath(suite.folder_path ?? "");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, suiteId]);

  async function handleSave() {
    if (!suiteId) return;
    setSaving(true);
    try {
      await updateSuite(suiteId, { name, description, folder_path: folderPath });
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Edit suite"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} isLoading={saving} disabled={!name.trim()}>
            Save
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="flex h-32 items-center justify-center">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Name" required>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </Field>
          <Field label="Folder path">
            <input
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </Field>
          <Field label="Description">
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </Field>
        </div>
      )}
    </Modal>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}
