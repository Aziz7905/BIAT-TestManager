import type { ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import ProtectedRoute from "./ProtectedRoute";
import LoginPage from "../pages/LoginPage";
import ProjectsPage from "../pages/ProjectsPage";
import ProjectWorkspacePage from "../pages/ProjectWorkspacePage";
import ProfilePage from "../pages/ProfilePage";
import UsersPage from "../pages/admin/UsersPage";
import TeamsPage from "../pages/admin/TeamsPage";

// Users admin: only org_admin + platform_owner
function AdminOnlyRoute({ children }: { children: ReactNode }) {
  const hasHydrated = useAuthStore((s) => s.hasHydrated);
  const role = useAuthStore((s) => s.user?.profile?.organization_role);
  const isAdmin = role === "platform_owner" || role === "org_admin";

  if (!hasHydrated) return null;
  return isAdmin ? <>{children}</> : <Navigate to="/projects" replace />;
}

// Teams: org_admin + platform_owner + team managers
function TeamsRoute({ children }: { children: ReactNode }) {
  const hasHydrated = useAuthStore((s) => s.hasHydrated);
  const user = useAuthStore((s) => s.user);

  if (!hasHydrated) return null;

  const role = user?.profile?.organization_role;
  const isAdmin = role === "platform_owner" || role === "org_admin";
  const isManager = user?.profile?.team_memberships?.some((m) => m.role === "manager") ?? false;

  return (isAdmin || isManager) ? <>{children}</> : <Navigate to="/projects" replace />;
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectWorkspacePage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route
            path="/admin/users"
            element={<AdminOnlyRoute><UsersPage /></AdminOnlyRoute>}
          />
          <Route
            path="/admin/teams"
            element={<TeamsRoute><TeamsPage /></TeamsRoute>}
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
