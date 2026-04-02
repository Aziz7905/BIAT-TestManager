/** Dismissible inline error banner with warm contrast and clear hierarchy. */
import { useState } from "react";

interface ErrorMessageProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
}

export function ErrorMessage({
  message,
  onDismiss,
  className = "",
}: Readonly<ErrorMessageProps>) {
  const [isVisible, setIsVisible] = useState(true);

  const handleDismiss = () => {
    setIsVisible(false);
    onDismiss?.();
  };

  if (!isVisible || !message) {
    return null;
  }

  return (
    <div
      className={`rounded-2xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm text-red-600 shadow-sm ${className}`}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-4">
        <span>{message}</span>

        {onDismiss ? (
          <button
            type="button"
            onClick={handleDismiss}
            className="text-red-500 transition hover:text-red-700"
            aria-label="Dismiss error"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        ) : null}
      </div>
    </div>
  );
}
