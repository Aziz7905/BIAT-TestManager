import Button from "./Button";

interface PaginationControlsProps {
  page: number;
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  itemLabel: string;
  onNext: () => void;
  onPrevious: () => void;
  className?: string;
}

export default function PaginationControls({
  page,
  totalCount,
  hasNext,
  hasPrevious,
  itemLabel,
  onNext,
  onPrevious,
  className = "",
}: PaginationControlsProps) {
  return (
    <div
      className={[
        "flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-3",
        className,
      ].join(" ")}
    >
      <p className="text-xs text-slate-500">
        {totalCount === 0 ? `No ${itemLabel}` : `Page ${page} - ${totalCount} ${itemLabel} total`}
      </p>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="secondary" onClick={onPrevious} disabled={!hasPrevious}>
          Previous
        </Button>
        <Button size="sm" variant="secondary" onClick={onNext} disabled={!hasNext}>
          Next
        </Button>
      </div>
    </div>
  );
}
