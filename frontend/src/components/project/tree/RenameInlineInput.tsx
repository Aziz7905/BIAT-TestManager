import { useState } from "react";

interface RenameInlineInputProps {
  value: string;
  onCommit: (value: string) => void;
  onCancel: () => void;
}

export default function RenameInlineInput({
  value,
  onCommit,
  onCancel,
}: RenameInlineInputProps) {
  const [draft, setDraft] = useState(value);

  return (
    <input
      autoFocus
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          if (draft.trim()) {
            onCommit(draft.trim());
          }
        }
        if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
        }
      }}
      onBlur={() => {
        if (draft.trim() && draft.trim() !== value) {
          onCommit(draft.trim());
          return;
        }
        onCancel();
      }}
      className="min-w-0 flex-1 rounded border border-blue-400 bg-white px-2 py-0.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />
  );
}
