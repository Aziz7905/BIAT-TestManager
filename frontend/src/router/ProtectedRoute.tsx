/** Route guard with a branded loading state for authenticated app sections. */
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import type { UserProfileRole } from "../types/accounts";

interface ProtectedRouteProps {
  allowedRoles?: UserProfileRole[];
}

function getDefaultPathByRole(role: UserProfileRole | undefined): string {
  if (role === "platform_owner" || role === "org_admin") {
    return "/admin/users";
  }

  return "/home";
}

export default function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuthStore();
  const location = useLocation();

  // ======================
  // LOADING STATE
  // ======================
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-sm text-muted">
        Loading...
      </div>
    );
  }

  // ======================
  // NOT AUTHENTICATED
  // ======================
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // ======================
  // ROLE CHECK
  // ======================
  if (allowedRoles && !allowedRoles.includes(user.profile.role)) {
    return <Navigate to={getDefaultPathByRole(user.profile.role)} replace state={{ from: location }} />;
  }

  return <Outlet />;
}
