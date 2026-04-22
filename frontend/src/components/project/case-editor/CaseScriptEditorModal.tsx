import { useEffect, useState } from "react";
import { createScript, updateScript } from "../../../api/automation/scripts";
import type { AutomationScript } from "../../../types/automation";
import Button from "../../ui/Button";
import Modal from "../../ui/Modal";

interface CaseScriptEditorModalProps {
  open: boolean;
  testCaseId: string;
  script: AutomationScript | null;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
}

export default function CaseScriptEditorModal({
  open,
  testCaseId,
  script,
  onClose,
  onSaved,
}: CaseScriptEditorModalProps) {
  const [scriptContent, setScriptContent] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const isEditing = Boolean(script);

  useEffect(() => {
    if (!open) return;
    setScriptContent(script?.script_content ?? "");
    setSaveError(null);
  }, [open, script]);

  async function handleSave() {
    const content = scriptContent.trim();
    if (!content) return;

    setIsSaving(true);
    setSaveError(null);
    try {
      if (script) {
        await updateScript(script.id, { script_content: content });
      } else {
        await createScript({
          test_case: testCaseId,
          framework: "selenium",
          language: "python",
          script_content: content,
          generated_by: "user",
          is_active: true,
        });
      }
      await onSaved();
      onClose();
    } catch {
      setSaveError("Failed to save script. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEditing ? "Edit code" : "Add code"}
      size="xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} isLoading={isSaving} loadingText="Saving">
            Save code
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          {isEditing
            ? "Update the script linked to this case."
            : "Create a new Selenium / Python script for this case."}
        </p>
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
          Framework: {script?.framework || "selenium"} · Language: {script?.language || "python"}
        </div>
        {saveError && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{saveError}</p>
        )}
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
            Script content
          </span>
          <textarea
            value={scriptContent}
            onChange={(event) => setScriptContent(event.target.value)}
            rows={18}
            spellCheck={false}
            className="w-full rounded-md border border-slate-300 bg-slate-950 px-3 py-3 font-mono text-xs leading-6 text-slate-100 outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
          />
        </label>
      </div>
    </Modal>
  );
}
