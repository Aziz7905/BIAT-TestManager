/** Project workspace list and membership management restyled with branded surfaces. */
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getAdminUsers } from "../api/accounts/users";
import { getTeams } from "../api/accounts/teams";
import {
  addProjectMember,
  createProject,
  deleteProject,
  getProjectMembers,
  getProjects,
  removeProjectMember,
  updateProject,
  updateProjectMember,
} from "../api/projects";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { FormSelect } from "../components/FormSelect";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import { Badge, EmptyState } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type { AdminUser, Team } from "../types/accounts";
import type {
  Project,
  ProjectCreatePayload,
  ProjectMember,
  ProjectMemberRole,
  ProjectStatus,
  ProjectUpdatePayload,
} from "../types/projects";

function extractErrorMessage(data: unknown): string | null {
  if (typeof data === "string" && data.trim()) {
    return data;
  }

  if (Array.isArray(data)) {
    for (const item of data) {
      const message = extractErrorMessage(item);
      if (message) {
        return message;
      }
    }
  }

  if (typeof data === "object" && data !== null) {
    for (const value of Object.values(data)) {
      const message = extractErrorMessage(value);
      if (message) {
        return message;
      }
    }
  }

  return null;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as {
      response?: { data?: unknown };
    }).response;

    return extractErrorMessage(response?.data) || fallback;
  }

  return fallback;
}

const PROJECT_STATUS_OPTIONS: Array<{ value: ProjectStatus; label: string }> = [
  { value: "active", label: "active" },
  { value: "archived", label: "archived" },
];

const PROJECT_MEMBER_ROLE_OPTIONS: Array<{
  value: ProjectMemberRole;
  label: string;
}> = [
  { value: "owner", label: "owner" },
  { value: "editor", label: "editor" },
  { value: "viewer", label: "viewer" },
];

const initialProjectForm: ProjectCreatePayload = {
  team: "",
  name: "",
  description: "",
  status: "active",
};

function ProjectStackIcon() {
  return (
    <svg className="h-10 w-10" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <rect x="8" y="10" width="32" height="10" rx="4" className="stroke-primary" strokeWidth="2.5" />
      <rect x="12" y="21" width="24" height="8" rx="4" className="stroke-primary-light" strokeWidth="2.5" />
      <rect x="16" y="31" width="16" height="7" rx="3.5" className="stroke-warm" strokeWidth="2.5" />
    </svg>
  );
}

function getProjectStatusVariant(status: ProjectStatus) {
  return status === "active" ? "verified" : "warm";
}

export default function ProjectsPage() {
  const { user } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const role = user?.profile?.role;
  const isPlatformOwner = role === "platform_owner";
  const isOrgAdmin = role === "org_admin";
  const isTeamManager = role === "team_manager";
  const canManageProjects = isPlatformOwner || isOrgAdmin || isTeamManager;
  const projectWorkspaceBasePath = location.pathname.startsWith("/admin/")
    ? "/admin/projects"
    : "/projects";

  const [projects, setProjects] = useState<Project[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [isProjectModalOpen, setIsProjectModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);

  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([]);
  const [isMembersModalOpen, setIsMembersModalOpen] = useState(false);
  const [isMembersLoading, setIsMembersLoading] = useState(false);
  const [isMemberSaving, setIsMemberSaving] = useState(false);
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);
  const [deletingMemberId, setDeletingMemberId] = useState<string | null>(null);

  const [projectForm, setProjectForm] =
    useState<ProjectCreatePayload>(initialProjectForm);
  const [memberForm, setMemberForm] = useState<{
    userId: string;
    role: ProjectMemberRole;
  }>({
    userId: "",
    role: "viewer",
  });

  const teamOptions = useMemo(
    () =>
      teams.map((team) => ({
        value: team.id,
        label: `${team.name} - ${team.organization_name}`,
      })),
    [teams]
  );

  const availableProjectMembers = useMemo(() => {
    if (!selectedProject) {
      return [];
    }

    const existingUserIds = new Set(projectMembers.map((member) => member.user_id));

    return users.filter((appUser) => {
      const userRole = appUser.profile?.role;
      const isOnProjectTeam =
        appUser.profile?.team_memberships?.some(
          (membership) =>
            membership.team === selectedProject.team && membership.is_active
        ) ?? false;

      return (
        !existingUserIds.has(appUser.id) &&
        isOnProjectTeam &&
        (userRole === "team_manager" ||
          userRole === "tester" ||
          userRole === "viewer")
      );
    });
  }, [users, selectedProject, projectMembers]);

  const projectMemberOptions = availableProjectMembers.map((appUser) => ({
    value: String(appUser.id),
    label: `${appUser.first_name} ${appUser.last_name} - ${appUser.email}`,
  }));

  const loadProjectMembers = async (projectId: string): Promise<void> => {
    try {
      setIsMembersLoading(true);
      const members = await getProjectMembers(projectId);
      setProjectMembers(members);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load project members."));
    } finally {
      setIsMembersLoading(false);
    }
  };

  const loadData = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const projectsData = await getProjects();
      setProjects(projectsData);

      if (canManageProjects) {
        const [teamsData, usersData] = await Promise.all([
          getTeams(),
          getAdminUsers(),
        ]);
        setTeams(teamsData);
        setUsers(usersData);
        return;
      }

      setTeams([]);
      setUsers([]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load projects."));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [role]);

  const openCreateModal = (): void => {
    const defaultTeam = teams.length === 1 ? teams[0].id : "";

    setEditingProject(null);
    setProjectForm({
      ...initialProjectForm,
      team: defaultTeam,
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsProjectModalOpen(true);
  };

  const openEditModal = (project: Project): void => {
    setEditingProject(project);
    setProjectForm({
      team: project.team,
      name: project.name,
      description: project.description ?? "",
      status: project.status,
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsProjectModalOpen(true);
  };

  const closeProjectModal = (): void => {
    setIsProjectModalOpen(false);
    setEditingProject(null);
    setProjectForm(initialProjectForm);
  };

  const openMembersModal = async (project: Project): Promise<void> => {
    setSelectedProject(project);
    setProjectMembers([]);
    setMemberForm({
      userId: "",
      role: "viewer",
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsMembersModalOpen(true);
    await loadProjectMembers(project.id);
  };

  const closeMembersModal = (): void => {
    setIsMembersModalOpen(false);
    setSelectedProject(null);
    setProjectMembers([]);
    setMemberForm({
      userId: "",
      role: "viewer",
    });
  };

  const handleProjectSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      if (editingProject) {
        const payload: ProjectUpdatePayload = {
          team: projectForm.team,
          name: projectForm.name.trim(),
          description: projectForm.description?.trim() || "",
          status: projectForm.status ?? "active",
        };

        await updateProject(editingProject.id, payload);
        setSuccessMessage("Project updated successfully.");
      } else {
        const payload: ProjectCreatePayload = {
          team: projectForm.team,
          name: projectForm.name.trim(),
          description: projectForm.description?.trim() || "",
          status: projectForm.status ?? "active",
        };

        await createProject(payload);
        setSuccessMessage("Project created successfully.");
      }

      await loadData();
      closeProjectModal();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save project."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteProject = async (projectId: string): Promise<void> => {
    const confirmed = globalThis.confirm(
      "Are you sure you want to delete this project?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingProjectId(projectId);
      setErrorMessage("");
      setSuccessMessage("");

      await deleteProject(projectId);
      setSuccessMessage("Project deleted successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete project."));
    } finally {
      setDeletingProjectId(null);
    }
  };

  const handleAddProjectMember = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    if (!selectedProject || !memberForm.userId) {
      return;
    }

    try {
      setIsMemberSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      await addProjectMember(selectedProject.id, {
        user: Number(memberForm.userId),
        role: memberForm.role,
      });

      setSuccessMessage("Project member added successfully.");
      setMemberForm({
        userId: "",
        role: "viewer",
      });
      await Promise.all([loadData(), loadProjectMembers(selectedProject.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to add project member."));
    } finally {
      setIsMemberSaving(false);
    }
  };

  const handleProjectMemberRoleChange = async (
    member: ProjectMember,
    nextRole: ProjectMemberRole
  ): Promise<void> => {
    if (!selectedProject || member.role === nextRole) {
      return;
    }

    try {
      setUpdatingMemberId(member.id);
      setErrorMessage("");
      setSuccessMessage("");

      await updateProjectMember(selectedProject.id, member.id, {
        role: nextRole,
      });

      setSuccessMessage("Project member updated successfully.");
      await Promise.all([loadData(), loadProjectMembers(selectedProject.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update project member."));
    } finally {
      setUpdatingMemberId(null);
    }
  };

  const handleRemoveProjectMember = async (
    member: ProjectMember
  ): Promise<void> => {
    if (!selectedProject) {
      return;
    }

    const confirmed = globalThis.confirm(
      `Remove ${member.full_name} from ${selectedProject.name}?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingMemberId(member.id);
      setErrorMessage("");
      setSuccessMessage("");

      await removeProjectMember(selectedProject.id, member.id);
      setSuccessMessage("Project member removed successfully.");
      await Promise.all([loadData(), loadProjectMembers(selectedProject.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to remove project member."));
    } finally {
      setDeletingMemberId(null);
    }
  };

  let projectsContent: ReactNode;

  if (isLoading) {
    projectsContent = (
      <div className="flex min-h-[220px] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  } else if (projects.length === 0) {
    projectsContent = (
      <div className="p-6">
        <EmptyState
          icon={<ProjectStackIcon />}
          title="No projects yet"
          description="Create a project to connect teams, specifications, and the QA work that will feed the next testing layers."
          primaryAction={
            canManageProjects ? (
              <Button onClick={openCreateModal}>New Project</Button>
            ) : undefined
          }
        />
      </div>
    );
  } else {
    projectsContent = (
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-bg">
          <tr>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Project
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Team
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Organisation
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Status
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Members
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Created By
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Actions
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-border">
          {projects.map((project) => {
            const isDeletingThisProject = deletingProjectId === project.id;

            return (
              <tr key={project.id} className="transition hover:bg-bg">
                <td className="px-6 py-4 text-sm text-text">
                  <Link
                    to={`${projectWorkspaceBasePath}/${project.id}`}
                    className="font-semibold tracking-tight text-text transition hover:text-primary"
                  >
                    {project.name}
                  </Link>
                  <div className="mt-1 text-xs text-muted">
                    {project.description || "No description"}
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {project.team_name}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {project.organization_name}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  <Badge variant={getProjectStatusVariant(project.status)}>
                    {project.status}
                  </Badge>
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {project.member_count > 0
                    ? project.member_names.join(", ")
                    : "-"}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {project.created_by_name ?? "-"}
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => navigate(`${projectWorkspaceBasePath}/${project.id}`)}
                    >
                      Open
                    </Button>

                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => void openMembersModal(project)}
                    >
                      Members
                    </Button>

                    {canManageProjects ? (
                      <>
                        <Button
                          variant="secondary"
                          size="md"
                          onClick={() => openEditModal(project)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          size="md"
                          onClick={() => void handleDeleteProject(project.id)}
                          isLoading={isDeletingThisProject}
                          loadingText="Deleting..."
                        >
                          Delete
                        </Button>
                      </>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Badge variant="tag">Project workspace</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text">Projects</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {canManageProjects
              ? "Manage the project directory, then open each project as its own QA workspace with linked specifications, members, and test suites."
              : "Open the projects you are assigned to and work from the project-level QA workspace."}
          </p>
        </div>

        {canManageProjects ? <Button onClick={openCreateModal}>New Project</Button> : null}
      </div>

      {successMessage ? (
        <div className="rounded-2xl border border-status-verified-text/15 bg-status-verified-bg px-4 py-3 text-sm text-status-verified-text shadow-sm">
          {successMessage}
        </div>
      ) : null}

      {errorMessage ? (
        <ErrorMessage
          message={errorMessage}
          onDismiss={() => setErrorMessage("")}
          className="mb-4"
        />
      ) : null}

      <div className="overflow-hidden rounded-[28px] border border-border bg-surface shadow-panel">
        {projectsContent}
      </div>

      <Modal
        isOpen={isProjectModalOpen}
        onClose={closeProjectModal}
        title={editingProject ? "Edit Project" : "Create Project"}
        size="lg"
      >
        <form onSubmit={handleProjectSubmit} className="space-y-4">
          <FormSelect
            id="project-team"
            label="Team"
            value={projectForm.team}
            onChange={(event) =>
              setProjectForm((previousForm) => ({
                ...previousForm,
                team: event.target.value,
              }))
            }
            options={teamOptions}
            placeholder="Select team"
            required
            disabled={Boolean(editingProject && editingProject.member_count > 0)}
            helperText={
              editingProject && editingProject.member_count > 0
                ? "Move or remove current project members before changing the team."
                : undefined
            }
          />

          <FormInput
            id="project-name"
            label="Project name"
            type="text"
            value={projectForm.name}
            onChange={(event) =>
              setProjectForm((previousForm) => ({
                ...previousForm,
                name: event.target.value,
              }))
            }
            required
          />

          <div>
            <label
              htmlFor="project-description"
              className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-muted"
            >
              Description
            </label>
            <textarea
              id="project-description"
              value={projectForm.description ?? ""}
              onChange={(event) =>
                setProjectForm((previousForm) => ({
                  ...previousForm,
                  description: event.target.value,
                }))
              }
              rows={4}
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-text outline-none transition placeholder:text-muted focus-visible:ring-4 focus-visible:ring-primary-light/20"
            />
          </div>

          <FormSelect
            id="project-status"
            label="Status"
            value={projectForm.status ?? "active"}
            onChange={(event) =>
              setProjectForm((previousForm) => ({
                ...previousForm,
                status: event.target.value as ProjectStatus,
              }))
            }
            options={PROJECT_STATUS_OPTIONS}
            required
          />

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={closeProjectModal}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSaving} loadingText="Saving...">
              {editingProject ? "Update" : "Create"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isMembersModalOpen}
        onClose={closeMembersModal}
        title={selectedProject ? `${selectedProject.name} Members` : "Project Members"}
        size="xl"
      >
        <div className="space-y-6">
          {canManageProjects && selectedProject ? (
            <form
              onSubmit={handleAddProjectMember}
              className="rounded-[28px] border border-border bg-bg p-5"
            >
              <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
                <FormSelect
                  id="project-member-user"
                  label="User"
                  value={memberForm.userId}
                  onChange={(event) =>
                    setMemberForm((previousForm) => ({
                      ...previousForm,
                      userId: event.target.value,
                    }))
                  }
                  options={projectMemberOptions}
                  placeholder="Select user"
                  required
                />

                <FormSelect
                  id="project-member-role"
                  label="Project role"
                  value={memberForm.role}
                  onChange={(event) =>
                    setMemberForm((previousForm) => ({
                      ...previousForm,
                      role: event.target.value as ProjectMemberRole,
                    }))
                  }
                  options={PROJECT_MEMBER_ROLE_OPTIONS}
                  required
                />
              </div>

              <div className="mt-4 flex justify-end">
                <Button
                  type="submit"
                  isLoading={isMemberSaving}
                  loadingText="Adding..."
                  disabled={projectMemberOptions.length === 0}
                >
                  Add Member
                </Button>
              </div>

              {projectMemberOptions.length === 0 ? (
                <p className="mt-3 text-sm text-muted">
                  No more team members are available to add to this project.
                </p>
              ) : null}
            </form>
          ) : null}

          {isMembersLoading ? (
            <div className="flex min-h-[180px] items-center justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : projectMembers.length === 0 ? (
            <div className="rounded-[28px] border border-dashed border-border bg-surface p-6 text-sm text-muted">
              No project members found.
            </div>
          ) : (
            <div className="overflow-hidden rounded-[28px] border border-border bg-surface shadow-sm">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-bg">
                  <tr>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Name
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Email
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      User Role
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Project Role
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Actions
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-border">
                  {projectMembers.map((member) => {
                    const isUpdatingThisMember = updatingMemberId === member.id;
                    const isDeletingThisMember = deletingMemberId === member.id;
                    const isBusy = isUpdatingThisMember || isDeletingThisMember;

                    return (
                      <tr key={member.id} className="transition hover:bg-bg">
                        <td className="px-6 py-4 text-sm font-medium text-text">
                          {member.full_name}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted">
                          {member.email}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted">
                          {member.user_role}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted">
                          {canManageProjects ? (
                            <select
                              value={member.role}
                              onChange={(event) =>
                                void handleProjectMemberRoleChange(
                                  member,
                                  event.target.value as ProjectMemberRole
                                )
                              }
                              disabled={isBusy}
                              className="rounded-2xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none transition focus-visible:ring-4 focus-visible:ring-primary-light/20"
                            >
                              {PROJECT_MEMBER_ROLE_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          ) : (
                            member.role
                          )}
                        </td>
                        <td className="px-6 py-4 text-right text-sm">
                          {canManageProjects ? (
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => void handleRemoveProjectMember(member)}
                              isLoading={isDeletingThisMember}
                              loadingText="Removing..."
                            >
                              Remove
                            </Button>
                          ) : (
                            <span className="text-muted">View only</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
