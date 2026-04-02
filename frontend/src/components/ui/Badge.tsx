/** Branded badge variants for status, priority, and tag display. */
import type { ReactNode } from "react";

type BadgeVariant =
  | "tag"
  | "unverified"
  | "verified"
  | "automated"
  | "warm"
  | "priority-high"
  | "priority-medium"
  | "priority-low";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  tag: "border border-primary-light/20 bg-tag-fill text-primary",
  unverified: "border border-status-unverified-text/10 bg-status-unverified-bg text-status-unverified-text",
  verified: "border border-status-verified-text/10 bg-status-verified-bg text-status-verified-text",
  automated: "border border-primary bg-status-automated-bg text-status-automated-text",
  warm: "border border-warm/10 bg-warm/10 text-warm",
  "priority-high": "border border-red-200 bg-red-50 text-red-500",
  "priority-medium": "border border-amber-200 bg-amber-50 text-amber-500",
  "priority-low": "border border-gray-200 bg-gray-50 text-gray-400",
};

export function Badge({
  children,
  variant = "tag",
  className = "",
}: Readonly<BadgeProps>) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
