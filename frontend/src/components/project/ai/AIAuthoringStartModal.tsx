import { useState, type FormEvent } from "react";
import type { ExecutionBrowser } from "../../../types/automation";
import type { StartAIAuthoringSessionPayload } from "../../../types/ai";
import { Button, ErrorMessage, Input, Modal } from "../../ui";

const BROWSER_OPTIONS: ExecutionBrowser[] = ["chromium", "chrome"];
const MAX_STEPS_MIN = 2;
const MAX_STEPS_MAX = 50;
const TEMPERATURE_MIN = 0;
const TEMPERATURE_MAX = 1;
const MAX_TOKENS_MIN = 50;
const MAX_TOKENS_MAX = 2000;

function clampNumber(value: number, min: number, max: number, fallback: number) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}

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
  const [temperature, setTemperature] = useState(0);
  const [maxTokensPerStep, setMaxTokensPerStep] = useState(500);
  const [browser, setBrowser] = useState<ExecutionBrowser>("chromium");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedUrl = targetUrl.trim();
    if (!trimmedUrl) return;
    void onSubmit({
      test_case: testCaseId,
      target_url: trimmedUrl,
      max_steps: maxSteps,
      temperature,
      max_tokens_per_step: maxTokensPerStep,
      browser,
      platform: "desktop",
    });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Author with AI"
      size="lg"
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
            min={MAX_STEPS_MIN}
            max={MAX_STEPS_MAX}
            value={maxSteps}
            onChange={(event) =>
              setMaxSteps(
                Math.round(
                  clampNumber(
                    Number(event.target.value),
                    MAX_STEPS_MIN,
                    MAX_STEPS_MAX,
                    MAX_STEPS_MIN
                  )
                )
              )
            }
          />
        </div>

        <details className="rounded-md border border-slate-200 px-3 py-3">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">
            Advanced
          </summary>
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Temperature"
              type="number"
              min={TEMPERATURE_MIN}
              max={TEMPERATURE_MAX}
              step={0.1}
              value={temperature}
              onChange={(event) =>
                setTemperature(
                  clampNumber(
                    Number(event.target.value),
                    TEMPERATURE_MIN,
                    TEMPERATURE_MAX,
                    TEMPERATURE_MIN
                  )
                )
              }
            />
            <Input
              label="Max tokens per step"
              type="number"
              min={MAX_TOKENS_MIN}
              max={MAX_TOKENS_MAX}
              value={maxTokensPerStep}
              onChange={(event) =>
                setMaxTokensPerStep(
                  Math.round(
                    clampNumber(
                      Number(event.target.value),
                      MAX_TOKENS_MIN,
                      MAX_TOKENS_MAX,
                      500
                    )
                  )
                )
              }
            />
          </div>
        </details>
      </form>
    </Modal>
  );
}
