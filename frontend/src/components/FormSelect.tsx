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

    const borderClass = error ? "border-red-500" : "border-gray-300";

    return (
      <div className={containerClassName}>
        <label
          htmlFor={selectId}
          className="mb-1.5 block text-sm font-medium text-gray-700"
        >
          {label}
        </label>

        <select
          ref={ref}
          id={selectId}
          className={`w-full rounded-lg border px-4 py-2.5 text-sm outline-none focus:border-gray-900 ${borderClass} ${className}`}
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
          <p id={`${selectId}-error`} className="mt-1 text-sm text-red-600">
            {error}
          </p>
        ) : null}

        {!error && helperText ? (
          <p id={`${selectId}-helper`} className="mt-1 text-sm text-gray-500">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

FormSelect.displayName = "FormSelect";