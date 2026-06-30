import { Spinner } from "../../ui";
import type { AIGenerationSession } from "../../../types/ai";
import type { DraftStructureStats, GenerationEvent, LaunchContext } from "../testPilot.types";
import {
  ACTIVITY_EVENT_LIMIT,
  formatEventTime,
  friendlyEventLabel,
  hasTemporaryAttachmentContext,
} from "../testPilot.utils";

export function PromptSnapshot({
  session,
  initialContext,
}: Readonly<{ session: AIGenerationSession; initialContext: LaunchContext }>) {
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">Prompt</h2>
      <p className="mt-3 text-sm leading-6 text-slate-700">{session.objective}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {hasTemporaryAttachmentContext(session) ? <ContextChip label="Document attached" /> : null}
        {initialContext.selectionType && <ContextChip label={`Context: ${initialContext.selectionType}`} />}
      </div>
    </div>
  );
}

export function StatusBlock({
  session,
  selectedCount,
  structureStats,
}: Readonly<{
  session: AIGenerationSession;
  selectedCount: number;
  structureStats: DraftStructureStats;
}>) {
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-950">Generation</h2>
        <span className="rounded-full bg-[#EAF4FF] px-2.5 py-1 text-xs font-medium capitalize text-[#17233C]">
          {session.status.replaceAll("_", " ")}
        </span>
      </div>
      <p className="mt-3 text-xs font-medium uppercase tracking-wide text-slate-500">Repository shape</p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Metric label="Suites" value={String(structureStats.suiteCount)} />
        <Metric label="Sections" value={String(structureStats.sectionCount)} />
        <Metric label="Child sections" value={String(structureStats.childSectionCount)} />
        <Metric label="Scenarios" value={String(structureStats.scenarioCount)} />
        <Metric label="Cases" value={String(structureStats.caseCount)} />
        <Metric label="Selected" value={String(selectedCount)} />
      </div>
    </div>
  );
}

export function SelectedPlan({ scenarios }: Readonly<{ scenarios: Array<Record<string, unknown>> }>) {
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">Selected plan</h2>
      <div className="mt-3 space-y-2">
        {scenarios.map((scenario) => (
          <div
            key={String(scenario.draft_scenario_id ?? scenario.candidate_id)}
            className="rounded-lg bg-[#F8FBFF] px-3 py-2"
          >
            <div className="text-sm font-medium text-slate-800">{String(scenario.title ?? "Scenario")}</div>
            <div className="mt-1 text-xs text-slate-500">
              {String(scenario.category ?? "functional")} / {String(scenario.priority ?? "should_have")} /{" "}
              {String(scenario.intended_case_count ?? "?")} cases
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ActivityTimeline({
  events,
  running,
  headline,
}: Readonly<{ events: GenerationEvent[]; running: boolean; headline: string }>) {
  const visible = events.slice(-ACTIVITY_EVENT_LIMIT);
  return (
    <div className="rounded-xl border border-[#D9E8F7] bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        {running ? (
          <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
          </span>
        ) : (
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" aria-hidden="true" />
        )}
        <h2 className="text-sm font-semibold text-slate-950">{running ? "Thinking" : "Thought process"}</h2>
      </div>
      <p className="mt-1 text-sm font-medium text-slate-600">{headline}</p>
      <ol className="mt-4">
        {visible.length ? (
          visible.map((event, index) => {
            const isLast = index === visible.length - 1;
            return (
              <li key={`${event.type}-${index}`} className="relative flex gap-3 pb-4 last:pb-0">
                {!isLast && <span className="absolute left-[5px] top-3 h-full w-px bg-slate-200" aria-hidden="true" />}
                <span
                  className={[
                    "relative mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                    isLast && running ? "bg-sky-500" : "bg-slate-300",
                  ].join(" ")}
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-slate-800">{friendlyEventLabel(event.type)}</span>
                    {event.created_at && (
                      <span className="text-[11px] text-slate-400">{formatEventTime(event.created_at)}</span>
                    )}
                  </div>
                  {event.message && <p className="mt-0.5 text-sm leading-6 text-slate-500">{event.message}</p>}
                </div>
              </li>
            );
          })
        ) : (
          <li className="text-sm text-slate-500">Starting the generation session.</li>
        )}
      </ol>
    </div>
  );
}

export function GeneratingState({
  headline,
}: Readonly<{ headline: string }>) {
  return (
    <div className="flex h-full items-center justify-center px-4">
      <div className="w-full max-w-2xl rounded-2xl border border-[#D9E8F7] bg-white/92 p-7 text-center shadow-[0_18px_45px_rgba(11,23,51,0.08)]">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#EAF4FF]">
          <Spinner size="lg" />
        </div>
        <h2 className="mt-5 text-xl font-semibold text-[#17233C]">{headline}</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#64748B]">
          Planning candidate scenarios, selecting the strongest set, then expanding test cases.
        </p>
        <div className="mt-6 grid gap-3 text-left sm:grid-cols-3">
          {["Understanding context", "Selecting coverage", "Drafting cases"].map((item) => (
            <div key={item} className="rounded-lg border border-[#D9E8F7] bg-[#F8FBFF] px-3 py-2 text-xs font-semibold text-[#64748B]">
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ContextChip({ label }: Readonly<{ label: string }>) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
      {label}
    </span>
  );
}

function Metric({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-950">{value}</div>
    </div>
  );
}
