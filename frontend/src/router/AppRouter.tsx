/** Branded application shell and route map for the BIAT Test Manager frontend. */
import { useEffect } from "react";
import type { ReactElement } from "react";
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import LoginPage from "../pages/LoginPage";
import AdminUserPage from "../pages/AdminUserPage";
import OrganisationsPage from "../pages/OrganisationsPage";
import TeamsPage from "../pages/TeamsPage";
import ProfilePage from "../pages/ProfilePage";
import ProjectsPage from "../pages/ProjectsPage";
import ProjectWorkspacePage from "../pages/ProjectWorkspacePage";
import SpecificationsPage from "../pages/SpecificationsPage";
import ProtectedRoute from "./ProtectedRoute";
import { useAuthStore } from "../store/authStore";
import type { CurrentUser, UserProfileRole } from "../types/accounts";
import HomePage from "../pages/HomePage";
import { Button } from "../components/Button";
import { SidebarItem } from "../components/ui";

interface ShellNavItem {
  to: string;
  label: string;
  icon: ReactElement;
  exact?: boolean;
}

function HomeIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M3 10.75 12 4l9 6.75V20H3v-9.25Z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 20v-5h6v5" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 21v-2a4 4 0 0 0-3-3.87" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15.5 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function TeamsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" transform="translate(0 4)" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M5 21v-1a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v1" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M5 10a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 10a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
    </svg>
  );
}

function ProjectsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 6.5A2.5 2.5 0 0 1 6.5 4H10l2 2h5.5A2.5 2.5 0 0 1 20 8.5v9A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5v-11Z" />
    </svg>
  );
}

function SpecsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 4h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M14 4v5h5" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 13h6M9 17h6" />
    </svg>
  );
}

function ProfileIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M20 21v-1.5A4.5 4.5 0 0 0 15.5 15h-7A4.5 4.5 0 0 0 4 19.5V21" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
    </svg>
  );
}

function OrganisationIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M3 21h18" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M5 21V7l7-4 7 4v14" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 10h.01M15 10h.01M9 14h.01M15 14h.01" />
    </svg>
  );
}

function getHomePathByRole(user: CurrentUser | null): string {
  const role: UserProfileRole | undefined = user?.profile?.role;

  if (role === "platform_owner" || role === "org_admin") {
    return "/admin/users";
  }

  return "/home";
}

function getActiveLabel(items: ShellNavItem[], pathname: string): string {
  const match = items.find(
    (item) =>
      pathname === item.to ||
      pathname.startsWith(`${item.to}/`) ||
      (item.to !== "/home" && pathname.startsWith(item.to.replace(/\/$/, "")))
  );

  return match?.label ?? "Workspace";
}

function ShellLayout({
  items,
  caption,
}: Readonly<{
  items: ShellNavItem[];
  caption: string;
}>) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const activeLabel = getActiveLabel(items, location.pathname);
  const visibleItems = items.filter(Boolean);

  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="grid min-h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-r border-border bg-surface">
          <div className="flex h-full flex-col px-5 py-6">
            <div className="rounded-[28px] border border-border bg-bg p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-sm font-bold text-white">
                  BT
                </div>
                <div>
                  <p className="text-sm font-semibold tracking-tight text-text">
                    BIAT Test Manager
                  </p>
                  <p className="text-xs text-muted">{caption}</p>
                </div>
              </div>
            </div>

            <div className="mt-8">
              <p className="px-3 text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Workspace
              </p>
              <nav className="mt-3 space-y-1.5">
                {visibleItems.map((item) => (
                  <SidebarItem
                    key={item.to}
                    to={item.to}
                    label={item.label}
                    icon={item.icon}
                    exact={item.exact}
                  />
                ))}
              </nav>
            </div>

            <div className="mt-auto rounded-[28px] border border-border bg-bg p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Signed in as
              </p>
              <p className="mt-3 text-sm font-semibold text-text">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="mt-1 break-all text-sm text-muted">{user?.email}</p>
              <Button
                onClick={handleLogout}
                variant="secondary"
                className="mt-5 w-full justify-center"
              >
                Logout
              </Button>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-col">
          <header className="sticky top-0 z-20 border-b border-border bg-surface/95 backdrop-blur-sm">
            <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5 xl:px-10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                  BIAT IT Workspace
                </p>
                <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text">
                  {activeLabel}
                </h1>
              </div>

              <div className="rounded-2xl border border-border bg-bg px-4 py-3 text-right">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Active Role
                </p>
                <p className="mt-1 text-sm font-semibold capitalize text-primary">
                  {user?.profile?.role?.replaceAll("_", " ") ?? "member"}
                </p>
              </div>
            </div>
          </header>

          <main className="flex-1 px-6 py-8 xl:px-10">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

function AdminLayout() {
  const { user } = useAuthStore();
  const isPlatformOwner = user?.profile.role === "platform_owner";

  const items: ShellNavItem[] = [
    { to: "/admin/home", label: "Home", icon: <HomeIcon />, exact: true },
    { to: "/admin/users", label: "Users", icon: <UsersIcon /> },
    { to: "/admin/teams", label: "Teams", icon: <TeamsIcon /> },
    { to: "/admin/projects", label: "Projects", icon: <ProjectsIcon /> },
    { to: "/admin/specifications", label: "Specifications", icon: <SpecsIcon /> },
    { to: "/admin/profile", label: "Profile", icon: <ProfileIcon /> },
    ...(isPlatformOwner
      ? [
          {
            to: "/admin/organisations",
            label: "Organisations",
            icon: <OrganisationIcon />,
          },
        ]
      : []),
  ];

  return <ShellLayout items={items} caption="Administration" />;
}

function AppShell() {
  const { user } = useAuthStore();
  const isTeamManager = user?.profile.role === "team_manager";
  const canSeeProjects =
    user?.profile.role === "team_manager" ||
    user?.profile.role === "tester" ||
    user?.profile.role === "viewer";

  const items: ShellNavItem[] = [
    { to: "/home", label: "Home", icon: <HomeIcon />, exact: true },
    { to: "/profile", label: "Profile", icon: <ProfileIcon /> },
    ...(canSeeProjects
      ? [
          { to: "/projects", label: "Projects", icon: <ProjectsIcon /> },
          { to: "/specifications", label: "Specifications", icon: <SpecsIcon /> },
        ]
      : []),
    ...(isTeamManager
      ? [
          { to: "/team/members", label: "Team Members", icon: <UsersIcon /> },
          { to: "/my-teams", label: "My Teams", icon: <TeamsIcon /> },
        ]
      : []),
  ];

  return <ShellLayout items={items} caption="Workspace" />;
}

function RoleHomeRedirect() {
  const { user } = useAuthStore();
  return <Navigate to={getHomePathByRole(user)} replace />;
}

export default function AppRouter() {
  const { initializeAuth } = useAuthStore();

  useEffect(() => {
    void initializeAuth();
  }, [initializeAuth]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/home" element={<HomePage />} />
          <Route path="/profile" element={<ProfilePage />} />

          <Route
            element={
              <ProtectedRoute allowedRoles={["team_manager", "tester", "viewer"]} />
            }
          >
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId" element={<ProjectWorkspacePage />} />
            <Route
              path="/projects/:projectId/specifications"
              element={<ProjectWorkspacePage />}
            />
            <Route
              path="/projects/:projectId/members"
              element={<ProjectWorkspacePage />}
            />
            <Route
              path="/projects/:projectId/test-suites"
              element={<ProjectWorkspacePage />}
            />
            <Route path="/specifications" element={<SpecificationsPage />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={["team_manager"]} />}>
            <Route path="/team/members" element={<AdminUserPage />} />
            <Route path="/my-teams" element={<TeamsPage />} />
            <Route path="/team/settings" element={<Navigate to="/my-teams" replace />} />
          </Route>
        </Route>

        <Route
          element={
            <ProtectedRoute allowedRoles={["platform_owner", "org_admin"]} />
          }
        >
          <Route element={<AdminLayout />}>
            <Route path="/admin/home" element={<HomePage />} />
            <Route path="/admin/profile" element={<ProfilePage />} />
            <Route path="/admin/users" element={<AdminUserPage />} />
            <Route path="/admin/teams" element={<TeamsPage />} />
            <Route path="/admin/projects" element={<ProjectsPage />} />
            <Route path="/admin/projects/:projectId" element={<ProjectWorkspacePage />} />
            <Route
              path="/admin/projects/:projectId/specifications"
              element={<ProjectWorkspacePage />}
            />
            <Route
              path="/admin/projects/:projectId/members"
              element={<ProjectWorkspacePage />}
            />
            <Route
              path="/admin/projects/:projectId/test-suites"
              element={<ProjectWorkspacePage />}
            />
            <Route path="/admin/specifications" element={<SpecificationsPage />} />

            <Route element={<ProtectedRoute allowedRoles={["platform_owner"]} />}>
              <Route
                path="/admin/organisations"
                element={<OrganisationsPage />}
              />
            </Route>
          </Route>
        </Route>

        <Route path="/" element={<RoleHomeRedirect />} />
        <Route path="/admin" element={<RoleHomeRedirect />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
