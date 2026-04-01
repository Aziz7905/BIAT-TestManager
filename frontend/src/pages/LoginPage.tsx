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
    <div className="min-h-screen bg-white">
      <div className="grid min-h-screen lg:grid-cols-2">
        <div className="relative hidden overflow-hidden bg-[#eaf6fb] lg:flex lg:items-center lg:justify-center">
          <div className="absolute inset-0 bg-gradient-to-br from-[#eaf6fb] via-white to-[#d8eef8]" />

          <div className="relative z-10 w-full max-w-2xl px-10">
            <div className="mb-8">
              <div className="mb-4 flex items-center gap-3">
                <img
                  src="/biat_logo.png"
                  alt="BIAT IT"
                  className="h-10 w-auto"
                />
                <span className="text-lg font-semibold text-gray-900">
                  BIAT Test Manager
                </span>
              </div>

              <h1 className="text-4xl font-semibold leading-tight text-gray-900">
                Smarter test management for BIAT IT teams
              </h1>
              <p className="mt-4 max-w-xl text-base text-gray-600">
                Centralize users, teams, projects, and AI-powered testing
                workflows in one secure platform.
              </p>
            </div>

            <div className="overflow-hidden rounded-3xl border border-white/60 bg-white/60 shadow-2xl backdrop-blur">
              <video
                autoPlay
                muted
                playsInline
                loop
                preload="auto"
                poster="/videos/cotester_hero_video_poster.webp.mp4"
                className="h-full w-full object-cover"
              >
                <source
                  src="/videos/cotester_hero_video.webm.mp4"
                  type="video/webm"
                />
              </video>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center px-4 py-10 sm:px-6 lg:px-10">
          <div className="w-full max-w-md rounded-3xl border border-gray-200 bg-white p-8 shadow-sm">
            <div className="mb-8 lg:hidden">
              <div className="mb-4 flex items-center gap-3">
                <img
                  src="/biat_logo.png"
                  alt="BIAT IT"
                  className="h-10 w-auto"
                />
                <span className="text-lg font-semibold text-gray-900">
                  BIAT Test Manager
                </span>
              </div>
            </div>

            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-gray-900">
                Sign in
              </h2>
              <p className="mt-2 text-sm text-gray-600">
                Sign in with your email or username and password.
              </p>
            </div>

            {errorMessage ? (
              <ErrorMessage
                message={errorMessage}
                onDismiss={() => setErrorMessage("")}
                className="mb-4"
              />
            ) : null}

            <form onSubmit={handleSubmit}>
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
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />

              <Button
                type="submit"
                isLoading={isLoading}
                loadingText="Signing in..."
                className="mt-2 w-full"
                size="lg"
              >
                Sign in
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}