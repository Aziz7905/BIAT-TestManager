import { useState, type FormEvent } from "react";
import type { ExecutionBrowser } from "../../../types/automation";
import type { StartAIAuthoringSessionPayload } from "../../../types/ai";
import { Button, ErrorMessage, Input, Modal } from "../../ui";

const BROWSER_OPTIONS: ExecutionBrowser[] = ["chromium", "chrome"];

interface AIAuthoringStartModalProps {
  readonly open: boolean;
  readonly testCaseId: string;
  readonly testCaseTitle: string;
  readonly defaultTargetUrl?: string;
  readonly isSubmitting?: boolean;
  readonly error?: string | null;
  readonly onClose: () => void;
  readonly onSubmit: (payload: StartAIAuthoringSessionPayload) => void | Promise<void>;
}

export default function AIAuthoringStartModal({
  open,
  testCaseId,
  testCaseTitle,
  defaultTargetUrl = "",
  isSubmitting = false,
  error,
  onClose,
  onSubmit,
}: AIAuthoringStartModalProps) {
  const [targetUrl, setTargetUrl] = useState(defaultTargetUrl);
  const [maxSteps, setMaxSteps] = useState(12);
  const [browser, setBrowser] = useState<ExecutionBrowser>("chromium");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedUrl = targetUrl.trim();
    if (!trimmedUrl) return;
    void onSubmit({
      test_case: testCaseId,
      target_url: trimmedUrl,
      max_steps: maxSteps,
      browser,
      platform: "desktop",
    });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Author with AI"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="ai-authoring-start-form"
            isLoading={isSubmitting}
            loadingText="Starting"
            disabled={!targetUrl.trim()}
          >
            Start authoring
          </Button>
        </>
      }
    >
      <form id="ai-authoring-start-form" className="space-y-4" onSubmit={handleSubmit}>
        <div>
          <p className="truncate text-sm font-semibold text-slate-900">{testCaseTitle}</p>
          <p className="mt-1 text-xs text-slate-500">Desktop browser</p>
        </div>

        {error && <ErrorMessage message={error} />}

        <Input
          label="Target URL"
          value={targetUrl}
          onChange={(event) => setTargetUrl(event.target.value)}
          placeholder="https://example.test/login"
          autoFocus
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700">Browser</span>
            <select
              value={browser}
              onChange={(event) => setBrowser(event.target.value as ExecutionBrowser)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-transparent focus:ring-2 focus:ring-blue-600"
            >
              {BROWSER_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <Input
            label="Max steps"
            type="number"
            min={2}
            max={12}
            value={maxSteps}
            onChange={(event) =>
              setMaxSteps(Math.min(Math.max(Number(event.target.value) || 2, 2), 12))
            }
          />
        </div>
      </form>
    </Modal>
  );
}
