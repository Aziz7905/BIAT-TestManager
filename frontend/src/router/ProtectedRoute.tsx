import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

function FullscreenSpinner() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-slate-50">
      <div className="h-7 w-7 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
    </div>
  );
}

export default function ProtectedRoute() {
  const hasHydrated = useAuthStore((s) => s.hasHydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const sessionExpired = useAuthStore((s) => s.sessionExpired);
  const location = useLocation();

  if (!hasHydrated) {
    return <FullscreenSpinner />;
  }

  return isAuthenticated
    ? <Outlet />
    : (
        <Navigate
          to="/login"
          state={{
            from: location,
            reason: sessionExpired ? "expired" : undefined,
          }}
          replace
        />
      );
}
