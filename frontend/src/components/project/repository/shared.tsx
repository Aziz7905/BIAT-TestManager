import type { ReactNode } from "react";
import type {
  CaseWorkspace,
  LinkedSpec,
  RecentRunCard,
  RepositoryRecentActivity,
  RepositorySummary,
} from "../../../types/testing";
import { Badge } from "../../ui";

export type BadgeTone = "blue" | "green" | "red" | "yellow" | "orange" | "slate";

export function formatLabel(value: string | null | undefined) {
  if (!value) return "Not set";
  return value.replaceAll("_", " ");
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "No activity yet";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

export function formatPercent(value: number | null | undefined) {
  if (value == null) return "0%";
  return `${Math.round(value)}%`;
}

export function formatJson(value: Record<string, unknown>) {
  if (!value || Object.keys(value).length === 0) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

export function designTone(status: string): BadgeTone {
  if (status === "approved") return "green";
  if (status === "in_review") return "blue";
  if (status === "archived") return "slate";
  return "yellow";
}

export function automationTone(status: string): BadgeTone {
  if (status === "automated") return "green";
  if (status === "in_progress") return "orange";
  return "slate";
}

export function resultTone(status: string | null | undefined): BadgeTone {
  if (status === "passed") return "green";
  if (status === "failed") return "red";
  if (status === "error") return "orange";
  if (status === "skipped") return "slate";
  return "slate";
}

export function executionStatusTone(status: string | null | undefined): BadgeTone {
  if (status === "passed") return "green";
  if (status === "failed") return "red";
  if (status === "error") return "orange";
  if (status === "running") return "blue";
  if (status === "paused") return "yellow";
  if (status === "queued") return "slate";
  if (status === "cancelled") return "slate";
  return "slate";
}

export function priorityTone(priority: string): BadgeTone {
  if (priority === "critical") return "red";
  if (priority === "high") return "orange";
  if (priority === "medium") return "blue";
  return "slate";
}

export function PanelSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-slate-100 px-6 py-5 first:border-t-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Header({
  eyebrow,
  title,
  subtitle,
  badges,
  actions,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  badges?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="border-b border-slate-200 px-6 py-5">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {eyebrow}
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-2xl font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {badges}
          {actions}
        </div>
      </div>
    </header>
  );
}

export function MetricGrid({
  items,
}: {
  items: Array<{ label: string; value: ReactNode }>;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-md border border-slate-200 px-3 py-3">
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            {item.label}
          </div>
          <div className="mt-1 text-lg font-semibold text-slate-900">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

export function ActivitySummary({ snapshot }: { snapshot: RepositoryRecentActivity }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      <div className="rounded-md border border-slate-200 px-3 py-3">
        <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Last execution
        </div>
        <div className="mt-1 text-sm text-slate-700">{formatDateTime(snapshot.last_execution_at)}</div>
      </div>
      <div className="rounded-md border border-slate-200 px-3 py-3">
        <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Recent executions
        </div>
        <div className="mt-1 text-sm font-semibold text-slate-900">{snapshot.recent_execution_count}</div>
      </div>
      <div className="rounded-md border border-slate-200 px-3 py-3">
        <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Recent pass rate
        </div>
        <div className="mt-1 text-sm font-semibold text-slate-900">
          {formatPercent(snapshot.recent_pass_rate)}
        </div>
      </div>
    </div>
  );
}

export function LinkedSpecifications({ items }: { items: LinkedSpec[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">No linked specifications yet.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <span className="font-medium text-slate-900">{item.title}</span>
          {item.external_reference && (
            <span className="text-xs text-slate-500">{item.external_reference}</span>
          )}
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
            {formatLabel(item.source_type)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function SummaryBreakdown({ summary }: { summary: RepositorySummary }) {
  return (
    <MetricGrid
      items={[
        { label: "Suites", value: summary.suite_count ?? 0 },
        { label: "Scenarios", value: summary.scenario_count ?? 0 },
        { label: "Cases", value: summary.case_count ?? 0 },
        { label: "Automated", value: summary.automated_case_count ?? 0 },
        { label: "Approved", value: summary.approved_case_count ?? 0 },
        { label: "Draft", value: summary.draft_case_count ?? 0 },
        { label: "In review", value: summary.in_review_case_count ?? 0 },
        { label: "Manual", value: summary.manual_case_count ?? 0 },
      ]}
    />
  );
}

export function RecentRunItem({ run }: { run: RecentRunCard }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">{run.name}</div>
          <div className="mt-1 text-xs text-slate-500">
            {formatLabel(run.trigger_type)} / {run.created_by_name || "Unknown author"}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge label={formatLabel(run.status)} color={resultTone(run.status)} dot />
          <span className="text-xs text-slate-500">{formatPercent(run.pass_rate)}</span>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-500 md:grid-cols-4">
        <div>{run.run_case_count} cases</div>
        <div>{run.passed_case_count} passed</div>
        <div>{run.failed_case_count} failed</div>
        <div>{formatDateTime(run.started_at || run.created_at)}</div>
      </div>
    </div>
  );
}

export function CaseSummaryBadges({ testCase }: { testCase: CaseWorkspace }) {
  return (
    <>
      <Badge
        label={formatLabel(testCase.design.design_status)}
        color={designTone(testCase.design.design_status)}
        dot
      />
      <Badge
        label={formatLabel(testCase.design.automation_status)}
        color={automationTone(testCase.design.automation_status)}
      />
      <Badge
        label={
          testCase.automation.latest_execution
            ? formatLabel(testCase.automation.latest_execution.status)
            : "No result"
        }
        color={resultTone(testCase.automation.latest_execution?.status)}
        dot
      />
    </>
  );
}
