/** Branded home workspace with role-aware shortcuts and polished overview cards. */
import { Link } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { Badge, EmptyState } from "../components/ui";
import { Button } from "../components/Button";

function getWelcomeMessage(role: string | undefined): string {
  if (role === "team_manager") {
    return "Manage your teams, organize project work, and keep the testing workflow aligned with your QA process.";
  }

  if (role === "tester") {
    return "Access your assigned projects, review specifications, and stay focused on execution-ready work.";
  }

  if (role === "viewer") {
    return "Review shared project context, profile details, and the workspaces available to your team.";
  }

  return "Coordinate teams, projects, and AI-assisted testing work from one place.";
}

function FolderChecklistIcon() {
  return (
    <svg className="h-10 w-10" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <path
        d="M8 13.5A3.5 3.5 0 0 1 11.5 10H19l3 3h14.5A3.5 3.5 0 0 1 40 16.5v18A3.5 3.5 0 0 1 36.5 38h-25A3.5 3.5 0 0 1 8 34.5v-21Z"
        className="stroke-primary"
        strokeWidth="2.5"
      />
      <path d="m18 24 3 3 6-7" className="stroke-primary-light" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M26 29h8" className="stroke-warm" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
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
    <div className="space-y-8">
      <section className="overflow-hidden rounded-[32px] border border-border bg-surface shadow-panel">
        <div className="grid gap-8 px-8 py-8 xl:grid-cols-[minmax(0,1.2fr)_360px] xl:px-10 xl:py-10">
          <div>
            <Badge variant="tag">Workspace overview</Badge>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-text">
              {fullName || "BIAT Test Manager"}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted">
              {getWelcomeMessage(role)}
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={isAdmin ? "/admin/profile" : "/profile"}>
                <Button size="lg">Go to Profile</Button>
              </Link>

              {canSeeProjects ? (
                <Link to={isAdmin ? "/admin/projects" : "/projects"}>
                  <Button variant="secondary" size="lg">
                    Open Projects
                  </Button>
                </Link>
              ) : null}

              {canSeeSpecifications ? (
                <Link to={isAdmin ? "/admin/specifications" : "/specifications"}>
                  <Button variant="secondary" size="lg">
                    Open Specifications
                  </Button>
                </Link>
              ) : null}
            </div>
          </div>

          <div className="rounded-[28px] border border-border bg-bg p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Current context
            </p>
            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Role
                </p>
                <p className="mt-2 text-sm font-semibold capitalize text-primary">
                  {role ? role.replaceAll("_", " ") : "Unknown"}
                </p>
              </div>
              <div className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Organisation
                </p>
                <p className="mt-2 text-sm font-semibold text-text">
                  {user?.profile?.organization_name ?? "-"}
                </p>
              </div>
              <div className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                  Primary team
                </p>
                <p className="mt-2 text-sm font-semibold text-text">
                  {user?.profile?.team_name ?? "No team assigned"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <EmptyState
        icon={<FolderChecklistIcon />}
        title="Keep your testing workspace organized from day one"
        description="Start from imported specifications, review the normalized context, and keep team-level project work structured before generation and execution layers grow around it."
        primaryAction={
          canSeeSpecifications ? (
            <Link to={isAdmin ? "/admin/specifications" : "/specifications"}>
              <Button size="lg">Open Specifications</Button>
            </Link>
          ) : undefined
        }
        secondaryAction={
          canSeeProjects ? (
            <Link to={isAdmin ? "/admin/projects" : "/projects"}>
              <Button variant="secondary" size="lg">
                Open Projects
              </Button>
            </Link>
          ) : undefined
        }
      >
        <div className="grid gap-4 text-left lg:grid-cols-3">
          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Assigned email
            </p>
            <p className="mt-3 text-sm font-medium text-text">{user?.email ?? "-"}</p>
          </div>
          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Team workspace
            </p>
            <p className="mt-3 text-sm font-medium text-text">
              {role === "team_manager" ? "Team management enabled" : "Project-level access"}
            </p>
          </div>
          <div className="rounded-[24px] border border-border bg-bg p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Suggested next step
            </p>
            <p className="mt-3 text-sm font-medium text-text">
              {canSeeSpecifications ? "Review imported specification context" : "Update your profile and team settings"}
            </p>
          </div>
        </div>
      </EmptyState>
    </div>
  );
}
