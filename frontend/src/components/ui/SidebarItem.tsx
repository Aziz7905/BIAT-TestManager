/** Sidebar navigation item with active-state treatment tied to the brand palette. */
import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

interface SidebarItemProps {
  to: string;
  label: string;
  icon?: ReactNode;
  exact?: boolean;
}

export function SidebarItem({
  to,
  label,
  icon,
  exact = false,
}: Readonly<SidebarItemProps>) {
  return (
    <NavLink
      to={to}
      end={exact}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition ${
          isActive
            ? "bg-primary-light/10 text-primary"
            : "text-muted hover:bg-bg hover:text-text"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={`absolute inset-y-2 left-0 w-1 rounded-full ${
              isActive ? "bg-primary" : "bg-transparent"
            }`}
            aria-hidden="true"
          />
          <span className={`${isActive ? "text-primary" : "text-primary-light"}`}>{icon}</span>
          <span>{label}</span>
        </>
      )}
    </NavLink>
  );
}

