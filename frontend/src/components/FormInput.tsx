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

    const borderClass = error ? "border-red-500" : "border-gray-300";

    return (
      <div className={containerClassName}>
        <label
          htmlFor={inputId}
          className="mb-1.5 block text-sm font-medium text-gray-700"
        >
          {label}
        </label>

        <input
          ref={ref}
          id={inputId}
          className={`w-full rounded-lg border px-4 py-2.5 text-sm outline-none focus:border-gray-900 ${borderClass} ${className}`}
          aria-invalid={error ? "true" : "false"}
          aria-describedby={describedBy}
          {...props}
        />

        {error ? (
          <p id={`${inputId}-error`} className="mt-1 text-sm text-red-600">
            {error}
          </p>
        ) : null}

        {!error && helperText ? (
          <p id={`${inputId}-helper`} className="mt-1 text-sm text-gray-500">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

FormInput.displayName = "FormInput";