import { NavLink, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";

interface TopNavProps {
  projectName?: string;
}

interface NavItem {
  label: string;
  to: string;
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return [
    "rounded-md px-3 py-1.5 text-sm transition",
    isActive ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white",
  ].join(" ");
}

export default function TopNav({ projectName }: TopNavProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const displayName =
    user?.first_name && user?.last_name
      ? `${user.first_name} ${user.last_name}`
      : user?.username ?? "";

  const initials =
    user?.first_name && user?.last_name
      ? `${user.first_name[0]}${user.last_name[0]}`
      : (user?.username?.[0] ?? "?").toUpperCase();

  const isAdmin =
    user?.profile?.organization_role === "platform_owner" ||
    user?.profile?.organization_role === "org_admin";

  const isManager =
    user?.profile?.team_memberships?.some((m) => m.role === "manager") ?? false;

  const navItems: NavItem[] = [
    { label: "Profile", to: "/profile" },
  ];

  if (isAdmin) {
    navItems.unshift(
      { label: "Teams", to: "/admin/teams" },
      { label: "Users", to: "/admin/users" }
    );
  } else if (isManager) {
    navItems.unshift({ label: "Teams", to: "/admin/teams" });
  }

  navItems.push({ label: "Projects", to: "/projects" });

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="h-12 shrink-0 border-b border-slate-800 bg-slate-900 px-4">
      <div className="flex h-full items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          <button
            onClick={() => navigate("/projects")}
            className="flex items-center gap-2 hover:opacity-80 transition"
          >
            <img src="/biat_logo.png" alt="BIAT" className="h-6 w-6 rounded object-cover" />
            <span className="hidden text-sm font-semibold text-white sm:block">BIAT TM</span>
          </button>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}

            {projectName && (
              <>
                <span className="px-1 text-sm text-slate-500">/</span>
                <span className="truncate text-sm font-medium text-slate-300 max-w-[220px]">
                  {projectName}
                </span>
              </>
            )}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-slate-400 md:block">{displayName}</span>
          <div className="relative group">
            <button className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white transition hover:bg-blue-500">
              {initials}
            </button>
            <div className="absolute right-0 top-full z-50 mt-1 hidden w-48 rounded-lg border border-slate-100 bg-white py-1 shadow-lg group-focus-within:block group-hover:block">
              {navItems.map((item) => (
                <button
                  key={item.to}
                  onClick={() => navigate(item.to)}
                  className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                >
                  {item.label}
                </button>
              ))}
              <div className="my-1 border-t border-slate-100" />
              <button
                onClick={() => void handleLogout()}
                className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}