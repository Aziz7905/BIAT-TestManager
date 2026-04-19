import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white focus:ring-blue-600",
  secondary:
    "bg-white hover:bg-slate-50 disabled:opacity-50 text-slate-700 border border-slate-300 focus:ring-slate-400",
  ghost:
    "bg-transparent hover:bg-slate-100 disabled:opacity-50 text-slate-600 focus:ring-slate-400",
  danger:
    "bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white focus:ring-red-600",
};

const sizeClasses: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-3 text-sm",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
  loadingText?: string;
}

export default function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  loadingText,
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || isLoading}
      className={[
        "inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition",
        "focus:outline-none focus:ring-2 focus:ring-offset-2",
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(" ")}
      {...props}
    >
      {isLoading && (
        <svg className="animate-spin h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
      )}
      {isLoading && loadingText ? loadingText : children}
    </button>
  );
}
