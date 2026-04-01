import { useEffect } from "react";
import {
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import LoginPage from "../pages/LoginPage";
import AdminUserPage from "../pages/AdminUserPage";
import OrganisationsPage from "../pages/OrganisationsPage";
import TeamsPage from "../pages/TeamsPage";
import ProfilePage from "../pages/ProfilePage";
import ProjectsPage from "../pages/ProjectsPage";
import SpecificationsPage from "../pages/SpecificationsPage";
import ProtectedRoute from "./ProtectedRoute";
import { useAuthStore } from "../store/authStore";
import type { CurrentUser, UserProfileRole } from "../types/accounts";
import HomePage from "../pages/HomePage";

function getHomePathByRole(user: CurrentUser | null): string {
  const role: UserProfileRole | undefined = user?.profile?.role;

  if (role === "platform_owner" || role === "org_admin") {
    return "/admin/users";
  }

  return "/home";
}

function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const isPlatformOwner = user?.profile.role === "platform_owner";

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6 text-sm font-medium">
            <Link to="/admin/home" className="text-gray-700 hover:text-black">
              Home
            </Link>

            <Link to="/admin/users" className="text-gray-700 hover:text-black">
              Users
            </Link>

            <Link to="/admin/teams" className="text-gray-700 hover:text-black">
              Teams
            </Link>

            <Link to="/admin/projects" className="text-gray-700 hover:text-black">
              Projects
            </Link>

            <Link
              to="/admin/specifications"
              className="text-gray-700 hover:text-black"
            >
              Specifications
            </Link>

            <Link to="/admin/profile" className="text-gray-700 hover:text-black">
              Profile
            </Link>

            {isPlatformOwner ? (
              <Link
                to="/admin/organisations"
                className="text-gray-700 hover:text-black"
              >
                Organisations
              </Link>
            ) : null}
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium text-gray-900">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="text-xs text-gray-500">{user?.email}</p>
            </div>

            <button
              onClick={handleLogout}
              className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-red-700"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

function AppShell() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const isTeamManager = user?.profile.role === "team_manager";
  const canSeeProjects =
    user?.profile.role === "team_manager" ||
    user?.profile.role === "tester" ||
    user?.profile.role === "viewer";

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6 text-sm font-medium">
            <Link to="/home" className="text-gray-700 hover:text-black">
              Home
            </Link>

            <Link to="/profile" className="text-gray-700 hover:text-black">
              Profile
            </Link>

            {canSeeProjects ? (
              <Link to="/projects" className="text-gray-700 hover:text-black">
                Projects
              </Link>
            ) : null}

            {canSeeProjects ? (
              <Link to="/specifications" className="text-gray-700 hover:text-black">
                Specifications
              </Link>
            ) : null}

            {isTeamManager ? (
              <Link to="/team/members" className="text-gray-700 hover:text-black">
                Team Members
              </Link>
            ) : null}

            {isTeamManager ? (
              <Link to="/my-teams" className="text-gray-700 hover:text-black">
                My Teams
              </Link>
            ) : null}

          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium text-gray-900">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="text-xs text-gray-500">{user?.email}</p>
            </div>

            <button
              onClick={handleLogout}
              className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-red-700"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
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
