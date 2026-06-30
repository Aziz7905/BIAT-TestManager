import { useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { Button } from "../../ui";
import type { ComposerMode, DraftReference } from "../testPilot.types";
import { truncate } from "../testPilot.utils";
import { CloseIcon } from "../icons/TestPilotIcons";

export default function ConversationComposer({
  mode,
  references,
  onClarify,
  onRefine,
}: Readonly<{
  mode: ComposerMode;
  references: DraftReference[];
  onClarify: (answers: string) => Promise<void>;
  onRefine: (instruction: string, draftIds: string[]) => Promise<void>;
}>) {
  const [text, setText] = useState("");
  const [selectedRefs, setSelectedRefs] = useState<DraftReference[]>([]);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (mode === "hidden") return null;

  if (mode === "disabled") {
    return (
      <div className="border-t border-slate-200 bg-white px-5 py-4">
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
          <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
          </span>
          <span>TestPilot is working&hellip;</span>
        </div>
      </div>
    );
  }

  const isRefine = mode === "refine";
  const placeholder = isRefine
    ? "Refine the draft - e.g. add a negative case for expired tokens. Use @ to target a scenario or case."
    : "Answer the questions so TestPilot can continue.";

  function toggleRef(ref: DraftReference) {
    setSelectedRefs((current) =>
      current.some((item) => item.draft_id === ref.draft_id)
        ? current.filter((item) => item.draft_id !== ref.draft_id)
        : [...current, ref]
    );
    setMentionOpen(false);
  }

  async function submit() {
    const trimmed = text.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    try {
      if (isRefine) {
        await onRefine(trimmed, selectedRefs.map((ref) => ref.draft_id));
      } else {
        await onClarify(trimmed);
      }
      setText("");
      setSelectedRefs([]);
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  return (
    <div className="relative border-t border-slate-200 bg-white px-5 py-4">
      {isRefine && selectedRefs.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {selectedRefs.map((ref) => (
            <span
              key={ref.draft_id}
              className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700"
            >
              {ref.type === "scenario" ? "Scenario" : "Case"}: {truncate(ref.label, 26)}
              <button
                type="button"
                onClick={() => toggleRef(ref)}
                className="text-sky-400 hover:text-sky-700"
                aria-label={`Remove ${ref.label}`}
              >
                <CloseIcon className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      {mentionOpen && isRefine && (
        <div className="absolute inset-x-5 bottom-[96px] z-20 max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl">
          {references.length ? (
            references.map((ref) => (
              <button
                key={ref.draft_id}
                type="button"
                onClick={() => toggleRef(ref)}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <span className="truncate text-slate-700">{ref.label}</span>
                <span className="shrink-0 text-xs uppercase text-slate-400">{ref.type}</span>
              </button>
            ))
          ) : (
            <p className="px-3 py-2 text-sm text-slate-500">No scenarios or cases yet.</p>
          )}
        </div>
      )}
      <div className="rounded-lg border border-slate-200 bg-white focus-within:border-sky-400 focus-within:ring-2 focus-within:ring-sky-100">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          placeholder={placeholder}
          className="w-full resize-none border-0 bg-transparent px-3 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400"
        />
        <div className="flex items-center justify-between px-2 py-2">
          {isRefine ? (
            <button
              type="button"
              onClick={() => setMentionOpen((open) => !open)}
              className="rounded-md px-2 py-1 text-sm font-semibold text-slate-500 hover:bg-slate-100"
              title="Reference a scenario or case"
            >
              @
            </button>
          ) : (
            <span />
          )}
          <Button size="sm" isLoading={submitting} loadingText="Sending" onClick={() => void submit()}>
            {isRefine ? "Send" : "Answer"}
          </Button>
        </div>
      </div>
    </div>
  );
}

