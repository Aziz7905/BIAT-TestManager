/** Shared button styles aligned with the BIAT Test Manager brand palette. */
import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loadingText?: string;
  children: ReactNode;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "border border-[rgb(var(--color-primary))] bg-[rgb(var(--color-primary))] text-white shadow-sm hover:bg-[rgb(var(--color-primary))/0.94] disabled:hover:bg-[rgb(var(--color-primary))]",
  secondary:
    "border border-[rgb(var(--color-primary-light))] bg-transparent text-[rgb(var(--color-primary-light))] hover:bg-[rgb(var(--color-primary-light))/0.10] hover:text-[rgb(var(--color-primary))] disabled:hover:bg-transparent",
  danger:
    "border border-red-200 bg-white text-red-500 hover:bg-red-50 disabled:hover:bg-white",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-3 py-2 text-xs",
  md: "px-4 py-2.5 text-sm",
  lg: "px-5 py-3 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  loadingText = "Loading...",
  disabled = false,
  children,
  className = "",
  type = "button",
  ...props
}: Readonly<ButtonProps>) {
  const isDisabled = disabled || isLoading;
  const variantClass = VARIANT_CLASSES[variant];
  const sizeClass = SIZE_CLASSES[size];

  return (
    <button
      type={type}
      disabled={isDisabled}
      className={`inline-flex items-center justify-center rounded-2xl font-semibold tracking-tight transition focus-visible:ring-2 focus-visible:ring-[rgb(var(--color-primary-light))] focus-visible:ring-offset-2 focus-visible:ring-offset-[rgb(var(--color-surface))] disabled:cursor-not-allowed disabled:opacity-60 ${variantClass} ${sizeClass} ${className}`}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center justify-center">
          <svg
            className="-ml-1 mr-2 h-4 w-4 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          {loadingText}
        </span>
      ) : (
        children
      )}
    </button>
  );
}
