import { useState } from "react";
import type {
  AIGenerationCaseDraft,
  AIGenerationDraftPayload,
  AIGenerationScenarioDraft,
  AIGenerationSectionDraft,
} from "../../../types/ai";
import { collectSectionStats } from "../testPilot.utils";
import {
  ChevronRightIcon,
  ListIcon,
  PriorityIcon,
  WarningIcon,
} from "../icons/TestPilotIcons";

export default function DraftHierarchyView({
  activeDraftId,
  draft,
  emptyLabel,
  selectedCaseIds,
  onActivate,
  onToggleCase,
  onToggleScenario,
}: Readonly<{
  activeDraftId: string;
  draft: AIGenerationDraftPayload;
  emptyLabel?: string;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
  onToggleScenario: (scenario: AIGenerationScenarioDraft) => void;
}>) {
  return (
    <section className="min-h-0">
      <div className="space-y-4">
        {draft.sections.length ? draft.sections.map((section) => (
          <SectionTreeNode
            activeDraftId={activeDraftId}
            key={section.draft_id}
            section={section}
            selectedCaseIds={selectedCaseIds}
            onActivate={onActivate}
            onToggleCase={onToggleCase}
            onToggleScenario={onToggleScenario}
          />
        )) : (
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-12 text-center">
            <p className="text-sm font-medium text-slate-700">{emptyLabel ?? "No generated items yet."}</p>
          </div>
        )}
      </div>
    </section>
  );
}

function SectionTreeNode({
  activeDraftId,
  section,
  selectedCaseIds,
  onActivate,
  onToggleCase,
  onToggleScenario,
}: Readonly<{
  activeDraftId: string;
  section: AIGenerationSectionDraft;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
  onToggleScenario: (scenario: AIGenerationScenarioDraft) => void;
}>) {
  const [open, setOpen] = useState(true);
  const stats = collectSectionStats(section);
  return (
    <article className="rounded-xl border border-[#D9E8F7] bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 px-4 py-3.5">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
          aria-label={`${open ? "Collapse" : "Expand"} ${section.name}`}
          aria-expanded={open}
        >
          <ChevronRightIcon className={["h-5 w-5 transition", open ? "rotate-90" : ""].join(" ")} />
        </button>
        <button type="button" onClick={() => onActivate(section.draft_id)} className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-semibold text-slate-900">{section.name}</span>
          <span className="mt-0.5 block text-xs text-slate-500">
            {stats.scenarioCount} scenarios / {stats.caseCount} cases
          </span>
        </button>
      </div>
      {open && (
        <div className="border-t border-[#E4EEF8] bg-white">
          {section.scenarios.map((scenario) => (
            <ScenarioTreeNode
              activeDraftId={activeDraftId}
              key={scenario.draft_id}
              scenario={scenario}
              selectedCaseIds={selectedCaseIds}
              onActivate={onActivate}
              onToggleCase={onToggleCase}
              onToggleScenario={onToggleScenario}
            />
          ))}
          {section.children.map((child) => (
            <div key={child.draft_id} className="border-t border-[#E4EEF8] bg-[#F8FBFF] p-3">
              <SectionTreeNode
                activeDraftId={activeDraftId}
                section={child}
                selectedCaseIds={selectedCaseIds}
                onActivate={onActivate}
                onToggleCase={onToggleCase}
                onToggleScenario={onToggleScenario}
              />
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function ScenarioTreeNode({
  activeDraftId,
  scenario,
  selectedCaseIds,
  onActivate,
  onToggleCase,
  onToggleScenario,
}: Readonly<{
  activeDraftId: string;
  scenario: AIGenerationScenarioDraft;
  selectedCaseIds: Set<string>;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
  onToggleScenario: (scenario: AIGenerationScenarioDraft) => void;
}>) {
  const [open, setOpen] = useState(false);
  const selectedCount = scenario.cases.filter((testCase) => selectedCaseIds.has(testCase.draft_id)).length;
  const selected = scenario.cases.length > 0 && selectedCount === scenario.cases.length;
  const polarityCounts = collectScenarioPolarityCounts(scenario);
  return (
    <article className="border-t border-[#E4EEF8] first:border-t-0">
      <div
        className={[
          "grid items-center gap-3 px-4 py-3.5 transition md:grid-cols-[auto_auto_auto_minmax(0,1fr)_auto_auto]",
          activeDraftId === scenario.draft_id ? "bg-[#EAF4FF]" : "bg-white hover:bg-[#F8FBFF]",
        ].join(" ")}
      >
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
          aria-label={`${open ? "Collapse" : "Expand"} ${scenario.title}`}
          aria-expanded={open}
        >
          <ChevronRightIcon className={["h-5 w-5 transition", open ? "rotate-90" : ""].join(" ")} />
        </button>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleScenario(scenario)}
          className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          aria-label={`Select all cases in ${scenario.title}`}
        />
        <ListIcon className="h-5 w-5 text-slate-500" />
        <button type="button" onClick={() => onActivate(scenario.draft_id)} className="min-w-0 text-left">
          <span className="block truncate text-sm font-semibold text-slate-950">{scenario.title}</span>
          <span className="mt-1 line-clamp-2 block text-xs leading-5 text-slate-500">{scenario.description}</span>
        </button>
        <span className="flex flex-wrap items-center gap-2">
          <DraftPill label={scenario.business_priority ?? scenario.priority} />
          <ScenarioCaseCounters counts={polarityCounts} />
        </span>
      </div>
      {open && (
        <div className="divide-y divide-[#E4EEF8] border-t border-[#E4EEF8] bg-white">
          {scenario.cases.map((testCase) => (
            <CaseTreeRow
              active={activeDraftId === testCase.draft_id}
              key={testCase.draft_id}
              selected={selectedCaseIds.has(testCase.draft_id)}
              testCase={testCase}
              onActivate={onActivate}
              onToggleCase={onToggleCase}
            />
          ))}
        </div>
      )}
    </article>
  );
}

function ScenarioCaseCounters({ counts }: Readonly<{ counts: { positive: number; negative: number; edge: number } }>) {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold">
      <span className="text-emerald-600">{counts.positive}P</span>
      <span className="text-red-500">{counts.negative}N</span>
      <span className="text-slate-500">{counts.edge}E</span>
    </span>
  );
}

function collectScenarioPolarityCounts(scenario: AIGenerationScenarioDraft): { positive: number; negative: number; edge: number } {
  if (scenario.polarity === "negative") {
    return { positive: 0, negative: scenario.cases.length, edge: 0 };
  }
  const edgeCount = scenario.cases.filter((testCase) => testCase.warnings?.length).length;
  return { positive: Math.max(0, scenario.cases.length - edgeCount), negative: 0, edge: edgeCount };
}

function CaseTreeRow({
  active,
  selected,
  testCase,
  onActivate,
  onToggleCase,
}: Readonly<{
  active: boolean;
  selected: boolean;
  testCase: AIGenerationCaseDraft;
  onActivate: (draftId: string) => void;
  onToggleCase: (caseId: string) => void;
}>) {
  return (
    <div
      className={[
        "grid items-start gap-3 bg-white px-4 py-3.5 transition md:grid-cols-[auto_auto_minmax(0,1fr)_auto]",
        active ? "bg-[#EAF4FF]" : "hover:bg-[#F8FBFF]",
      ].join(" ")}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onToggleCase(testCase.draft_id)}
        className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
      />
      <WarningIcon className="mt-0.5 h-5 w-5 text-slate-500" />
      <button type="button" onClick={() => onActivate(testCase.draft_id)} className="min-w-0 text-left">
        <span className="block truncate text-sm font-semibold text-slate-900">{testCase.title}</span>
        <span className="mt-1 line-clamp-2 block text-xs leading-5 text-slate-500">{testCase.expected_result}</span>
        <span className="mt-2 flex flex-wrap items-center gap-2 text-[11px] font-medium text-slate-500">
          <PriorityIcon className="h-3.5 w-3.5 text-slate-400" />
          <span>Functional</span>
          <PolarityPill polarity={testCase.warnings?.length ? "edge" : "positive"} />
        </span>
      </button>
      <button
        type="button"
        onClick={() => onActivate(testCase.draft_id)}
        className="self-center text-slate-400 hover:text-slate-700"
        aria-label={`Open ${testCase.title}`}
      >
        <ChevronRightIcon className="h-5 w-5" />
      </button>
    </div>
  );
}

function PolarityPill({ polarity }: Readonly<{ polarity: string }>) {
  const normalized = polarity.toLowerCase();
  const className = normalized.includes("negative")
    ? "border-red-200 bg-red-50 text-red-700"
    : normalized.includes("edge") || normalized.includes("explor")
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${className}`}>
      {polarity.replaceAll("_", " ")}
    </span>
  );
}

function DraftPill({ label }: Readonly<{ label: string }>) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold capitalize text-slate-600">
      {label.replaceAll("_", " ")}
    </span>
  );
}

