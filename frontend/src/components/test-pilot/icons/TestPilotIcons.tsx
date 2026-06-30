type TestPilotIconProps = Readonly<{ className?: string }>;

export function ChevronRightIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="m7.5 4.5 5 5.5-5 5.5" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChevronDownIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="m5 7.5 5 5 5-5" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CloseIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="m5 5 10 10M15 5 5 15" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PlusIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="M10 4.5v11M4.5 10h11" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function TrashIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path
        d="M7.5 8v6M12.5 8v6M4.5 5.5h11M8 5.5l.5-1h3l.5 1M6 5.5l.6 10h6.8l.6-10"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ListIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="M7 5h9M7 10h9M7 15h9M4 5h.01M4 10h.01M4 15h.01" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function WarningIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="M10 3.5 17 16H3L10 3.5Z" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M10 7.5v4M10 14.25h.01" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PriorityIcon({ className = "h-5 w-5" }: TestPilotIconProps) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="M10 15.5v-11M5.5 9 10 4.5 14.5 9" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function DocumentStackIcon() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded bg-blue-50 text-blue-700" aria-hidden="true">
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 3h7l5 5v13H7z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 3v5h5M5 7H3v13h10" />
      </svg>
    </span>
  );
}

export function SpreadsheetIcon() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded bg-emerald-50 text-emerald-700" aria-hidden="true">
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 3h9l3 3v15H6z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 10h6M9 14h6M12 10v8" />
      </svg>
    </span>
  );
}

export function JiraLogo() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center text-blue-600" aria-hidden="true">
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12.2 3.4 20.6 12l-8.4 8.6-2.9-2.9 5.5-5.7-5.5-5.7 2.9-2.9Z" opacity=".85" />
        <path d="M5.8 3.4 14.2 12l-8.4 8.6L3 17.7 8.5 12 3 6.3l2.8-2.9Z" opacity=".55" />
      </svg>
    </span>
  );
}

