export function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-3 w-3 shrink-0 text-slate-400 transition-transform ${open ? "rotate-90" : ""}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
    </svg>
  );
}

export function SuiteIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
      <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
    </svg>
  );
}

export function SectionIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0 text-slate-400" fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function ScenarioIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function DotsIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
      <path d="M6.5 10a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0ZM11.5 10a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0ZM16.5 10a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0Z" />
    </svg>
  );
}

export function PencilIcon() {
  return (
    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15.232 5.232l3.536 3.536M4 16.5V20h3.5l9.94-9.94-3.536-3.536L4 16.5z"
      />
    </svg>
  );
}

export function TrashIcon() {
  return (
    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M8 7V5a1 1 0 011-1h6a1 1 0 011 1v2"
      />
    </svg>
  );
}

export function DuplicateIcon() {
  return (
    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 7V5a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2M8 7h8a2 2 0 012 2v8"
      />
    </svg>
  );
}

export function Dot({ tone }: { tone: string }) {
  return <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone}`} />;
}

export function CountChip({ value }: { value: number }) {
  return (
    <span className="inline-flex min-w-5 items-center justify-center rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
      {value}
    </span>
  );
}
