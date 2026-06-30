import type { AIGenerationDraftPayload } from "../../../types/ai";
import type { CoverageStats, DraftStats, ReviewFilterValue } from "../testPilot.types";
import { ChevronDownIcon } from "../icons/TestPilotIcons";

export default function DraftReviewToolbar({
  allVisibleCasesSelected,
  coverageStats,
  draft,
  draftStats,
  headline,
  priorityFilter,
  priorityOptions,
  progressPercent,
  query,
  running,
  typeFilter,
  typeOptions,
  visibleStats,
  visibleCaseCount,
  onPriorityFilterChange,
  onQueryChange,
  onToggleVisibleCases,
  onTypeFilterChange,
}: Readonly<{
  allVisibleCasesSelected: boolean;
  coverageStats: CoverageStats;
  draft: AIGenerationDraftPayload;
  draftStats: DraftStats;
  headline: string;
  priorityFilter: ReviewFilterValue;
  priorityOptions: string[];
  progressPercent: number;
  query: string;
  running: boolean;
  typeFilter: ReviewFilterValue;
  typeOptions: string[];
  visibleStats: DraftStats;
  visibleCaseCount: number;
  onPriorityFilterChange: (value: ReviewFilterValue) => void;
  onQueryChange: (query: string) => void;
  onToggleVisibleCases: () => void;
  onTypeFilterChange: (value: ReviewFilterValue) => void;
}>) {
  return (
    <div className="mb-5 rounded-2xl border border-[#D9E8F7] bg-white/95 p-4 shadow-sm">
      <div className="mb-4 border-b border-[#E4EEF8] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-600">
            Progress: <span className="font-semibold text-slate-950">{progressPercent}%</span>
          </div>
          <div className="text-sm font-semibold text-slate-500">{headline}</div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className={[
              "h-full rounded-full transition-all duration-500",
              running ? "bg-emerald-500" : "bg-blue-600",
            ].join(" ")}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-3 rounded-xl bg-[#F8FBFF] px-3 py-2 text-sm text-slate-600">
        <span className="font-medium text-slate-950">{draft.suite.name}</span>
        <span className="text-slate-300">/</span>
        <span>{draftStats.scenarioCount} scenarios</span>
        <span>{draftStats.caseCount} cases</span>
        <span className="text-emerald-700">{coverageStats.positiveScenarios}P</span>
        <span className="text-red-600">{coverageStats.negativeScenarios}N</span>
        {coverageStats.warningCount > 0 && <span className="text-amber-700">{coverageStats.warningCount} warnings</span>}
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex shrink-0 items-center gap-3">
          <input
            type="checkbox"
            checked={allVisibleCasesSelected}
            disabled={visibleCaseCount === 0}
            onChange={onToggleVisibleCases}
            className="h-5 w-5 rounded border-slate-300 text-blue-600"
            aria-label="Select all visible test cases"
          />
          <span className="text-sm font-semibold text-slate-600">{coverageStats.selectedCases}</span>
          <span className="text-sm text-slate-400">
            {visibleStats.scenarioCount} visible / {visibleCaseCount} cases
          </span>
        </div>
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search draft</span>
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400" aria-hidden="true">
            Search
          </span>
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search by test cases"
            className="h-10 w-full rounded-md border border-slate-300 bg-white pl-16 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <ToolbarSelect
            label="Type"
            value={typeFilter}
            options={typeOptions}
            onChange={onTypeFilterChange}
          />
          <ToolbarSelect
            label="Priority"
            value={priorityFilter}
            options={priorityOptions}
            onChange={onPriorityFilterChange}
          />
        </div>
      </div>
    </div>
  );
}

function ToolbarSelect({
  label,
  value,
  options,
  onChange,
}: Readonly<{
  label: string;
  value: ReviewFilterValue;
  options: string[];
  onChange: (value: ReviewFilterValue) => void;
}>) {
  return (
    <label className="relative">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 min-w-28 appearance-none rounded-md border border-slate-300 bg-white px-4 pr-9 text-sm font-semibold capitalize text-slate-600 outline-none transition hover:border-slate-400 hover:text-slate-950 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
        aria-label={`Filter by ${label.toLowerCase()}`}
      >
        <option value="all">{label}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replaceAll("_", " ")}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
        <ChevronDownIcon className="h-4 w-4 text-slate-400" />
      </span>
    </label>
  );
}
