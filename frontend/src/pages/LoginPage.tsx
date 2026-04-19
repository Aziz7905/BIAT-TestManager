import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button, ErrorMessage, Input } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type { User } from "../types/auth";

type LocationState = {
  from?: { pathname?: string };
  reason?: "expired";
};

function getErrorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string; error?: string } } }).response;
    return response?.data?.detail || response?.data?.error || "Login failed. Please check your credentials.";
  }
  return "Login failed. Please check your credentials.";
}

function getDefaultRedirectPath(user: User): string {
  const role = user.profile?.organization_role;
  if (role === "platform_owner" || role === "org_admin") return "/admin/users";
  return "/projects";
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    accessToken,
    hasHydrated,
    isAuthenticated,
    isLoading,
    login,
    sessionExpired,
    user,
  } = useAuthStore();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [videoUnavailable, setVideoUnavailable] = useState(false);

  const locationState = useMemo(() => {
    const state = location.state as LocationState | null;
    return {
      fromPath: state?.from?.pathname,
      reason: state?.reason,
    };
  }, [location.state]);

  const handleSubmit = async (event: { preventDefault(): void }) => {
    event.preventDefault();
    setErrorMessage("");
    try {
      await login(identifier, password);
      const authUser = useAuthStore.getState().user;
      const fallbackPath = authUser ? getDefaultRedirectPath(authUser) : "/projects";
      navigate(locationState.fromPath || fallbackPath, { replace: true });
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error));
    }
  };

  useEffect(() => {
    if (hasHydrated && isAuthenticated && user) {
      navigate(locationState.fromPath || getDefaultRedirectPath(user), {
        replace: true,
      });
    }
  }, [hasHydrated, isAuthenticated, locationState.fromPath, navigate, user]);

  useEffect(() => {
    if ((locationState.reason === "expired" || sessionExpired) && !isAuthenticated) {
      setErrorMessage("Your session expired. Please sign in again.");
    }
  }, [isAuthenticated, locationState.reason, sessionExpired]);

  if (!hasHydrated && accessToken) {
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-4 sm:px-6">
      <div className="grid min-h-[calc(100vh-2rem)] overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-lg lg:grid-cols-[minmax(0,1.1fr)_460px] xl:grid-cols-[minmax(0,1.16fr)_500px]">

        {/* ── Left — marketing ── */}
        <section className="relative hidden overflow-y-auto border-r border-slate-100 bg-white lg:block">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.08),transparent_42%),radial-gradient(circle_at_bottom_right,rgba(234,88,12,0.06),transparent_38%)]" />
          <div className="relative flex min-h-full flex-col px-10 py-8 xl:px-12">

            {/* Logo */}
            <div className="flex items-center gap-4">
              <img src="/biat_logo.png" alt="BIAT IT" className="h-11 w-auto" />
              <div>
                <p className="text-lg font-semibold tracking-tight text-slate-900">
                  BIAT Test Manager
                </p>
                <p className="text-sm text-slate-500">AI-native QA workspace</p>
              </div>
            </div>

            {/* Headline */}
            <div className="mt-10 max-w-xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-blue-500">
                Centralized QA operations
              </p>
              <h1 className="mt-4 max-w-lg text-4xl font-semibold leading-[1.1] tracking-tight text-slate-900 xl:text-[2.25rem]">
                Run structured QA work with cleaner context, teams, and project control.
              </h1>
            </div>

            {/* Video card */}
            <div className="mt-8 rounded-[28px] border border-slate-100 bg-slate-50 p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Product flow
                  </p>
                  <p className="mt-2 text-sm font-medium text-slate-800">
                    Watch the short pipeline overview.
                  </p>
                </div>
                <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
                  Pipeline
                </span>
              </div>

              {videoUnavailable ? (
                <div className="mt-4 flex min-h-[220px] items-center justify-center rounded-[24px] border border-dashed border-slate-200 bg-white px-8 text-center text-sm leading-6 text-slate-400">
                  The demo video could not be loaded — asset is at{" "}
                  <span className="mx-1 font-semibold text-slate-700">
                    public/videos/cotester_hero_video.webm.mp4
                  </span>
                </div>
              ) : (
                <div className="mt-4 overflow-hidden rounded-[24px] border border-slate-200 bg-[#05070b] p-2">
                  <video
                    className="max-h-[320px] w-full rounded-[20px] bg-[#05070b]"
                    src="/videos/cotester_hero_video.webm.mp4"
                    autoPlay
                    muted
                    loop
                    playsInline
                    controls
                    onError={() => setVideoUnavailable(true)}
                  />
                </div>
              )}
            </div>

          </div>
        </section>

        {/* ── Right — sign in ── */}
        <section className="flex items-start justify-center bg-white px-5 py-8 sm:px-8 lg:items-center lg:px-10 xl:px-12">
          <div className="w-full max-w-md">

            {/* Mobile logo */}
            <div className="mb-8 lg:hidden flex items-center gap-3">
              <img src="/biat_logo.png" alt="BIAT IT" className="h-10 w-auto" />
              <div>
                <p className="text-lg font-semibold tracking-tight text-slate-900">
                  BIAT Test Manager
                </p>
                <p className="text-sm text-slate-500">AI-native QA workspace</p>
              </div>
            </div>

            {/* Form card */}
            <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-7 shadow-sm xl:p-8">
              <div className="mb-7">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-blue-500">
                  Sign in
                </p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
                  Welcome back
                </h2>
                <p className="mt-3 text-sm leading-6 text-slate-500">
                  Sign in with your email or username and password to access your workspace.
                </p>
              </div>

              {errorMessage && (
                <ErrorMessage
                  message={errorMessage}
                  onDismiss={() => setErrorMessage("")}
                  className="mb-5"
                />
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <Input
                  id="identifier"
                  label="Email or username"
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="name.surname@biat-it.tn"
                  autoComplete="username"
                  required
                />
                <Input
                  id="password"
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
                <Button
                  type="submit"
                  isLoading={isLoading}
                  loadingText="Signing in…"
                  size="lg"
                  className="mt-2 w-full"
                >
                  Sign in
                </Button>
              </form>
            </div>

            <p className="mt-5 text-center text-xs text-slate-400">
              Contact your administrator to create or reset your account.
            </p>
          </div>
        </section>

      </div>
    </div>
  );
}
