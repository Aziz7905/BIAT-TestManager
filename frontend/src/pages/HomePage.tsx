import { Link } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

function getWelcomeMessage(role: string | undefined): string {
  if (role === "team_manager") {
    return "Manage your teams, organize project work, and follow testing activity.";
  }

  if (role === "tester") {
    return "Access your assigned projects, follow testing work, and review your activity.";
  }

  if (role === "viewer") {
    return "Review your assigned projects, your profile, and the information shared with your team.";
  }

  return "Welcome to BIAT Test Manager.";
}

export default function HomePage() {
  const { user } = useAuthStore();

  const role = user?.profile?.role;
  const fullName = `${user?.first_name ?? ""} ${user?.last_name ?? ""}`.trim();
  const isAdmin = role === "platform_owner" || role === "org_admin";
  const canSeeProjects =
    role === "platform_owner" ||
    role === "org_admin" ||
    role === "team_manager" ||
    role === "tester" ||
    role === "viewer";
  const canSeeSpecifications = canSeeProjects;

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-gray-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium text-sky-700">Welcome</p>
        <h1 className="mt-2 text-3xl font-semibold text-gray-900">
          {fullName || "BIAT Test Manager"}
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-gray-600">
          {getWelcomeMessage(role)}
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            to={isAdmin ? "/admin/profile" : "/profile"}
            className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
          >
            Go to Profile
          </Link>

          {canSeeProjects ? (
            <Link
              to={isAdmin ? "/admin/projects" : "/projects"}
              className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Open Projects
            </Link>
          ) : null}

          {canSeeSpecifications ? (
            <Link
              to={isAdmin ? "/admin/specifications" : "/specifications"}
              className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Open Specifications
            </Link>
          ) : null}

          {role === "team_manager" ? (
            <Link
              to="/team/members"
              className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Manage Team Members
            </Link>
          ) : null}

          {role === "team_manager" ? (
            <Link
              to="/my-teams"
              className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Open My Teams
            </Link>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Your role</h2>
          <p className="mt-2 text-sm text-gray-600">
            {role ? role.replaceAll("_", " ") : "Unknown"}
          </p>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Organisation</h2>
          <p className="mt-2 text-sm text-gray-600">
            {user?.profile?.organization_name ?? "-"}
          </p>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Team</h2>
          <p className="mt-2 text-sm text-gray-600">
            {user?.profile?.team_name ?? "No team assigned"}
          </p>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Email</h2>
          <p className="mt-2 text-sm text-gray-600">{user?.email ?? "-"}</p>
        </div>
      </div>
    </div>
  );
}
