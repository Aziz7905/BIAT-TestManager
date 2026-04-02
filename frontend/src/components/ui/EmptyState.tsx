/** Reusable empty state with aligned actions for onboarding and blank screens. */
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  children?: ReactNode;
}

export function EmptyState({
  icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  children,
}: Readonly<EmptyStateProps>) {
  return (
    <div className="rounded-[28px] border border-border bg-surface p-10 shadow-sm">
      <div className="mx-auto flex max-w-2xl flex-col items-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-3xl border border-primary-light/20 bg-primary-light/10 text-primary">
          {icon}
        </div>
        <h2 className="mt-6 text-2xl font-semibold tracking-tight text-text">{title}</h2>
        <p className="mt-3 max-w-xl text-sm leading-6 text-muted">{description}</p>
        {(primaryAction || secondaryAction) ? (
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {primaryAction}
            {secondaryAction}
          </div>
        ) : null}
        {children ? <div className="mt-10 w-full">{children}</div> : null}
      </div>
    </div>
  );
}

