/** Compact icon button with branded hover and focus states. */
import type { ButtonHTMLAttributes, ReactNode } from "react";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  label: string;
}

export function IconButton({
  icon,
  label,
  className = "",
  type = "button",
  ...props
}: Readonly<IconButtonProps>) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-muted transition hover:border-primary-light/40 hover:bg-primary-light/10 hover:text-primary focus-visible:ring-2 focus-visible:ring-primary-light focus-visible:ring-offset-2 focus-visible:ring-offset-surface ${className}`}
      {...props}
    >
      {icon}
    </button>
  );
}

