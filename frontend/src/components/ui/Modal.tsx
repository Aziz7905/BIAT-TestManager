/** Branded modal with sticky header and optional sticky footer slots. */
import { useEffect, useId, useRef } from "react";
import type { MouseEvent, ReactNode } from "react";

type ModalSize = "sm" | "md" | "lg" | "xl" | "full";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: ModalSize;
  footer?: ReactNode;
  actions?: ReactNode;
}

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: "max-w-xl",
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
  full: "max-w-[92rem]",
};

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  footer,
  actions,
}: Readonly<ModalProps>) {
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  const handleOverlayClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === overlayRef.current) {
      onClose();
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-text/40 px-4 py-5 backdrop-blur-sm"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className={`flex max-h-[92vh] w-full flex-col overflow-hidden rounded-[28px] border border-border bg-surface shadow-panel ${SIZE_CLASSES[size]}`}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/95 px-6 py-5 backdrop-blur-sm">
          <div>
            <h2 id={titleId} className="text-xl font-semibold tracking-tight text-text">
              {title}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {actions}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-muted transition hover:border-primary-light/40 hover:bg-primary-light/10 hover:text-primary"
              aria-label="Close modal"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">{children}</div>
        {footer ? (
          <div className="sticky bottom-0 z-10 border-t border-border bg-surface/95 px-6 py-4 backdrop-blur-sm">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
