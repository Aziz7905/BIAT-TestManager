/** Polished sign-in page aligned with the BIAT Test Manager brand system. */
import { useMemo, useState } from "react";
import type { SyntheticEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { useAuthStore } from "../store/authStore";
import type { CurrentUser, UserProfileRole } from "../types/accounts";

type LocationState = {
  from?: {
    pathname?: string;
  };
};

function getErrorMessage(error: unknown): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as {
      response?: { data?: { detail?: string; error?: string } };
    }).response;

    return (
      response?.data?.detail ||
      response?.data?.error ||
      "Login failed. Please check your credentials."
    );
  }

  return "Login failed. Please check your credentials.";
}

function getDefaultRedirectPath(user: CurrentUser): string {
  const role: UserProfileRole = user.profile.role;

  if (role === "platform_owner" || role === "org_admin") {
    return "/admin/users";
  }

  return "/home";
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading } = useAuthStore();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [videoUnavailable, setVideoUnavailable] = useState(false);

  const fromPath = useMemo(() => {
    const state = location.state as LocationState | null;
    return state?.from?.pathname;
  }, [location.state]);

  const handleSubmit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage("");

    try {
      await login(identifier, password);

      const authUser = useAuthStore.getState().user;
      const fallbackPath = authUser ? getDefaultRedirectPath(authUser) : "/profile";

      navigate(fromPath || fallbackPath, { replace: true });
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error));
    }
  };

  return (
    <div className="min-h-screen bg-bg px-4 py-4 sm:px-6">
      <div className="grid min-h-[calc(100vh-2rem)] overflow-hidden rounded-[32px] border border-border bg-surface shadow-panel lg:grid-cols-[minmax(0,1.1fr)_460px] xl:grid-cols-[minmax(0,1.16fr)_500px]">
        <section className="relative hidden overflow-y-auto border-r border-border bg-surface lg:block">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(74,144,196,0.18),transparent_42%),radial-gradient(circle_at_bottom_right,rgba(139,111,92,0.16),transparent_38%)]" />
          <div className="relative flex min-h-full flex-col px-10 py-8 xl:px-12">
            <div>
              <div className="flex items-center gap-4">
                <img
                  src="/biat_logo.png"
                  alt="BIAT IT"
                  className="h-11 w-auto"
                />
                <div>
                  <p className="text-lg font-semibold tracking-tight text-primary">
                    BIAT Test Manager
                  </p>
                  <p className="text-sm text-muted">AI-native QA workspace</p>
                </div>
              </div>

              <div className="mt-10 max-w-xl">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary-light">
                  Centralized QA operations
                </p>
                <h1 className="mt-4 max-w-lg text-4xl font-semibold leading-[1.1] tracking-tight text-text xl:text-[2.25rem]">
                  Run structured QA work with cleaner context, teams, and project control.
                </h1>
              </div>

              <div className="mt-8 rounded-[28px] border border-border bg-bg p-5 shadow-sm">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Product flow
                    </p>
                    <p className="mt-2 text-sm font-medium text-text">
                      Watch the short pipeline overview.
                    </p>
                  </div>
                  <span className="rounded-full border border-primary-light/20 bg-tag-fill px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                    Pipeline
                  </span>
                </div>

                {videoUnavailable ? (
                  <div className="mt-4 flex min-h-[220px] items-center justify-center rounded-[24px] border border-dashed border-border bg-surface px-8 text-center text-sm leading-6 text-muted">
                    The demo video could not be loaded here, but the product flow asset is still available in
                    <span className="mx-1 font-semibold text-text">public/videos/cotester_hero_video.webm.mp4</span>.
                  </div>
                ) : (
                  <div className="mt-4 overflow-hidden rounded-[24px] border border-border bg-[#05070b] p-2">
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
          </div>
        </section>

        <section className="flex items-start justify-center bg-surface px-5 py-8 sm:px-8 lg:items-center lg:px-10 xl:px-12">
          <div className="w-full max-w-md">
            <div className="mb-8 lg:hidden">
              <div className="flex items-center gap-3">
                <img
                  src="/biat_logo.png"
                  alt="BIAT IT"
                  className="h-10 w-auto"
                />
                <div>
                  <p className="text-lg font-semibold tracking-tight text-primary">
                    BIAT Test Manager
                  </p>
                  <p className="text-sm text-muted">AI-native QA workspace</p>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-border bg-bg p-7 shadow-sm xl:p-8">
              <div className="mb-7">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary-light">
                  Sign in
                </p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-text">
                  Welcome back
                </h2>
                <p className="mt-3 text-sm leading-6 text-muted">
                  Sign in with your email or username and password to access your workspace.
                </p>
              </div>

              {errorMessage ? (
                <ErrorMessage
                  message={errorMessage}
                  onDismiss={() => setErrorMessage("")}
                  className="mb-5"
                />
              ) : null}

              <form onSubmit={handleSubmit} className="space-y-5">
                <FormInput
                  id="identifier"
                  label="Email or username"
                  type="text"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  placeholder="name.surname@biat-it.tn"
                  autoComplete="username"
                  required
                />

                <FormInput
                  id="password"
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="********"
                  autoComplete="current-password"
                  required
                />

                <Button
                  type="submit"
                  isLoading={isLoading}
                  loadingText="Signing in..."
                  className="mt-2 w-full justify-center"
                  size="lg"
                >
                  Sign in
                </Button>
              </form>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
