/** Branded text input with consistent labels, helper text, and focus treatment. */
import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

interface FormInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  helperText?: string;
  containerClassName?: string;
}

export const FormInput = forwardRef<HTMLInputElement, FormInputProps>(
  (
    {
      label,
      error,
      helperText,
      id,
      className = "",
      containerClassName = "",
      ...props
    },
    ref
  ) => {
    const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
    const describedBy = error
      ? `${inputId}-error`
      : helperText
        ? `${inputId}-helper`
        : undefined;

    const borderClass = error
      ? "border-red-300 focus-visible:ring-red-200"
      : "border-border hover:border-primary-light/50 focus-visible:ring-primary-light/20";

    return (
      <div className={containerClassName}>
        <label
          htmlFor={inputId}
          className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
        >
          {label}
        </label>

        <input
          ref={ref}
          id={inputId}
          className={`w-full rounded-2xl border bg-surface px-4 py-3 text-sm text-text outline-none transition placeholder:text-muted focus-visible:ring-4 ${borderClass} ${className}`}
          aria-invalid={error ? "true" : "false"}
          aria-describedby={describedBy}
          {...props}
        />

        {error ? (
          <p id={`${inputId}-error`} className="mt-2 text-sm text-red-500">
            {error}
          </p>
        ) : null}

        {!error && helperText ? (
          <p id={`${inputId}-helper`} className="mt-2 text-sm text-muted">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

FormInput.displayName = "FormInput";
