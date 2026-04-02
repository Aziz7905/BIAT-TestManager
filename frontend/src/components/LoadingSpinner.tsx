/** Brand-colored loading spinner for async surfaces and modal states. */
type SpinnerSize = "sm" | "md" | "lg";

interface LoadingSpinnerProps {
  size?: SpinnerSize;
  className?: string;
  label?: string;
}

const SIZE_CLASSES: Record<SpinnerSize, string> = {
  sm: "h-4 w-4",
  md: "h-8 w-8",
  lg: "h-12 w-12",
};

export function LoadingSpinner({
  size = "md",
  className = "",
  label = "Loading",
}: Readonly<LoadingSpinnerProps>) {
  const sizeClass = SIZE_CLASSES[size];

  return (
    <div
      className={`flex items-center justify-center ${className}`}
      role="status"
      aria-label={label}
    >
      <div
        className={`${sizeClass} animate-spin rounded-full border-2 border-primary-light/25 border-t-primary`}
        aria-hidden="true"
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}
