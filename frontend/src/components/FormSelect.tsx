/** Branded select field with palette-safe focus and helper messaging. */
import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

interface SelectOption {
  value: string;
  label: string;
}

interface FormSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
  placeholder?: string;
  containerClassName?: string;
}

export const FormSelect = forwardRef<HTMLSelectElement, FormSelectProps>(
  (
    {
      label,
      options,
      error,
      helperText,
      placeholder,
      id,
      className = "",
      containerClassName = "",
      ...props
    },
    ref
  ) => {
    const selectId = id ?? label.toLowerCase().replace(/\s+/g, "-");
    const describedBy = error
      ? `${selectId}-error`
      : helperText
        ? `${selectId}-helper`
        : undefined;

    const borderClass = error
      ? "border-red-300 focus-visible:ring-red-200"
      : "border-border hover:border-primary-light/50 focus-visible:ring-primary-light/20";

    return (
      <div className={containerClassName}>
        <label
          htmlFor={selectId}
          className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
        >
          {label}
        </label>

        <select
          ref={ref}
          id={selectId}
          className={`w-full rounded-2xl border bg-surface px-4 py-3 text-sm text-text outline-none transition focus-visible:ring-4 ${borderClass} ${className}`}
          aria-invalid={error ? "true" : "false"}
          aria-describedby={describedBy}
          {...props}
        >
          {placeholder ? (
            <option value="" disabled>
              {placeholder}
            </option>
          ) : null}

          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        {error ? (
          <p id={`${selectId}-error`} className="mt-2 text-sm text-red-500">
            {error}
          </p>
        ) : null}

        {!error && helperText ? (
          <p id={`${selectId}-helper`} className="mt-2 text-sm text-muted">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

FormSelect.displayName = "FormSelect";
