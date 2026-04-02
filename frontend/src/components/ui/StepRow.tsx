/** Two-column step row for test step and expected outcome editing surfaces. */
import type { ReactNode, TextareaHTMLAttributes } from "react";

interface StepPaneProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
}

interface StepRowProps {
  index: number;
  left: StepPaneProps;
  right: StepPaneProps;
  actions?: ReactNode;
  isEditing?: boolean;
}

function StepPane({ label, className = "", ...props }: Readonly<StepPaneProps>) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">{label}</p>
      <textarea
        className={`mt-3 min-h-28 w-full resize-none border-0 bg-transparent p-0 text-sm leading-6 text-text outline-none placeholder:text-muted ${className}`}
        {...props}
      />
    </div>
  );
}

export function StepRow({
  index,
  left,
  right,
  actions,
  isEditing = false,
}: Readonly<StepRowProps>) {
  return (
    <div
      className={`grid gap-4 rounded-[24px] border border-border bg-surface p-4 shadow-sm xl:grid-cols-[56px_minmax(0,1fr)_auto] ${
        isEditing ? "ring-2 ring-primary-light/35" : ""
      }`}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-bg text-sm font-semibold text-primary">
        {index}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <StepPane {...left} />
        <StepPane {...right} />
      </div>
      {actions ? <div className="flex items-start justify-end gap-2">{actions}</div> : null}
    </div>
  );
}

