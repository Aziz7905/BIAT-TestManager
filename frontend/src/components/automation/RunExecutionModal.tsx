import { useEffect, useState } from "react";

import { Button } from "../Button";
import { FormSelect } from "../FormSelect";
import { Modal } from "../Modal";
import type {
  ExecutionBrowser,
  ExecutionPlatform,
} from "../../types/automation";

interface RunExecutionPayload {
  browser: ExecutionBrowser;
  platform: ExecutionPlatform;
}

interface RunExecutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: RunExecutionPayload) => Promise<void>;
  isSubmitting?: boolean;
  defaultBrowser?: ExecutionBrowser;
  defaultPlatform?: ExecutionPlatform;
}

interface RunExecutionFormState {
  browser: ExecutionBrowser;
  platform: ExecutionPlatform;
}

const browserOptions = [
  { value: "chromium", label: "Chromium" },
  { value: "chrome", label: "Chrome" },
  { value: "firefox", label: "Firefox" },
  { value: "webkit", label: "WebKit" },
  { value: "edge", label: "Edge" },
];

const platformOptions = [
  { value: "desktop", label: "Desktop" },
  { value: "mobile", label: "Mobile emulation" },
];

export function RunExecutionModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  defaultBrowser = "chromium",
  defaultPlatform = "desktop",
}: Readonly<RunExecutionModalProps>) {
  const [form, setForm] = useState<RunExecutionFormState>({
    browser: defaultBrowser,
    platform: defaultPlatform,
  });

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setForm({
      browser: defaultBrowser,
      platform: defaultPlatform,
    });
  }, [defaultBrowser, defaultPlatform, isOpen]);

  const handleSubmit = async () => {
    await onSubmit({
      browser: form.browser,
      platform: form.platform,
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Run Test Case"
      size="md"
    >
      <div className="space-y-4">
        <p className="text-sm leading-6 text-muted">
          {/* Temporary v1 execution config. Real live execution can replace this with
              richer runner/device capabilities later without changing the case detail flow. */}
          Choose the execution target for this run. Mobile currently means browser-based mobile emulation, not a real device cloud.
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          <FormSelect
            id="execution-browser"
            label="Browser"
            value={form.browser}
            onChange={(event) =>
              setForm((previous) => ({
                ...previous,
                browser: event.target.value as ExecutionBrowser,
              }))
            }
            options={browserOptions}
          />

          <FormSelect
            id="execution-platform"
            label="Platform"
            value={form.platform}
            onChange={(event) =>
              setForm((previous) => ({
                ...previous,
                platform: event.target.value as ExecutionPlatform,
              }))
            }
            options={platformOptions}
          />
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => void handleSubmit()}
            isLoading={isSubmitting}
            loadingText="Queueing..."
          >
            Run
          </Button>
        </div>
      </div>
    </Modal>
  );
}
