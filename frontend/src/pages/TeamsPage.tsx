/** Team management workspace aligned with the branded shell and data surfaces. */
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  addTeamMember,
  createTeam,
  deleteTeam,
  getTeamMembers,
  getTeams,
  removeTeamMember,
  updateTeamMember,
  updateTeam,
} from "../api/accounts/teams";
import { getOrganizations } from "../api/accounts/organizations";
import { getAdminUsers } from "../api/accounts/users";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { FormSelect } from "../components/FormSelect";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import { Badge } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type {
  AdminUser,
  Organization,
  Team,
  TeamCreatePayload,
  TeamMember,
  TeamMembershipRole,
  TeamUpdatePayload,
} from "../types/accounts";

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

const DEFAULT_TOKEN_BUDGET = 100000;
const ALL_MEMBERSHIP_ROLE_OPTIONS: Array<{
  value: TeamMembershipRole;
  label: string;
}> = [
  { value: "manager", label: "manager" },
  { value: "tester", label: "tester" },
  { value: "viewer", label: "viewer" },
];

const TEAM_MANAGER_ROLE_OPTIONS: Array<{
  value: TeamMembershipRole;
  label: string;
}> = [
  { value: "tester", label: "tester" },
  { value: "viewer", label: "viewer" },
];

const initialForm: TeamCreatePayload = {
  organization: "",
  name: "",
  manager: null,
  ai_provider: null,
  ai_api_key: null,
  ai_model: "",
  monthly_token_budget: DEFAULT_TOKEN_BUDGET,
  jira_base_url: "",
  jira_project_key: "",
  github_org: "",
  github_repo: "",
  jenkins_url: "",
};

export default function TeamsPage() {
  const { user } = useAuthStore();

  const role = user?.profile?.role;
  const isPlatformOwner = role === "platform_owner";
  const isOrgAdmin = role === "org_admin";
  const isTeamManager = role === "team_manager";
  const canManageTeams = isPlatformOwner || isOrgAdmin || isTeamManager;

  const [teams, setTeams] = useState<Team[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [deletingTeamId, setDeletingTeamId] = useState<string | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [isMembersModalOpen, setIsMembersModalOpen] = useState(false);
  const [isMembersLoading, setIsMembersLoading] = useState(false);
  const [isMemberSaving, setIsMemberSaving] = useState(false);
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);
  const [deletingMemberId, setDeletingMemberId] = useState<string | null>(null);

  const [form, setForm] = useState<TeamCreatePayload>(initialForm);
  const [memberForm, setMemberForm] = useState<{
    userId: string;
    role: TeamMembershipRole;
    isPrimary: boolean;
  }>({
    userId: "",
    role: "tester",
    isPrimary: false,
  });

  const currentOrganizationId = user?.profile.organization;
  const currentOrganizationName = user?.profile.organization_name;
  const canAddMembers = isPlatformOwner || isOrgAdmin;

  const currentOrganizationOption = useMemo<Organization[]>(
    () =>
      currentOrganizationId && currentOrganizationName
        ? [
            {
              id: currentOrganizationId,
              name: currentOrganizationName,
              domain: "",
              logo: null,
              created_at: "",
            },
          ]
        : [],
    [currentOrganizationId, currentOrganizationName]
  );

  const visibleOrganizations = useMemo(() => {
    if (isPlatformOwner) {
      return organizations;
    }

    return organizations.filter(
      (organization) => organization.id === currentOrganizationId
    );
  }, [organizations, isPlatformOwner, currentOrganizationId]);

  const visibleTeams = useMemo(() => {
    if (isPlatformOwner || isOrgAdmin) {
      return teams;
    }

    if (isTeamManager) {
      return teams;
    }

    return teams;
  }, [teams, isPlatformOwner, isOrgAdmin, isTeamManager]);

  const availableManagers = useMemo(() => {
    return users.filter((appUser) => {
      const userOrganizationId = appUser.profile?.organization;
      const userRole = appUser.profile?.role;

      if (userRole !== "team_manager") {
        return false;
      }

      if (!form.organization) {
        return true;
      }

      return userOrganizationId === form.organization;
    });
  }, [users, form.organization]);

  const availableMembers = useMemo(() => {
    if (!selectedTeam) {
      return [];
    }

    const existingUserIds = new Set(teamMembers.map((member) => member.user_id));

    return users.filter((appUser) => {
      const userRole = appUser.profile?.role;
      return (
        appUser.profile?.organization === selectedTeam.organization &&
        !existingUserIds.has(appUser.id) &&
        (userRole === "team_manager" ||
          userRole === "tester" ||
          userRole === "viewer")
      );
    });
  }, [users, selectedTeam, teamMembers]);

  const memberOptions = availableMembers.map((appUser) => ({
    value: String(appUser.id),
    label: `${appUser.first_name} ${appUser.last_name} - ${appUser.email}`,
  }));

  const organizationOptions = visibleOrganizations.map((organization) => ({
    value: organization.id,
    label: organization.name,
  }));

  const managerOptions = availableManagers.map((appUser) => ({
    value: String(appUser.id),
    label: `${appUser.first_name} ${appUser.last_name} - ${appUser.email}`,
  }));

  const getDefaultMembershipRole = (
    appUser: AdminUser | undefined
  ): TeamMembershipRole => {
    if (appUser?.profile?.role === "team_manager") {
      return "manager";
    }

    if (appUser?.profile?.role === "viewer") {
      return "viewer";
    }

    return "tester";
  };

  const loadMembersForTeam = async (teamId: string): Promise<void> => {
    try {
      setIsMembersLoading(true);
      const members = await getTeamMembers(teamId);
      setTeamMembers(members);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load team members."));
    } finally {
      setIsMembersLoading(false);
    }
  };

  const loadData = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const teamsData = await getTeams();
      setTeams(teamsData);

      if (isPlatformOwner) {
        const [organizationsData, usersData] = await Promise.all([
          getOrganizations(),
          getAdminUsers(),
        ]);
        setOrganizations(organizationsData);
        setUsers(usersData);
        return;
      }

      if (isOrgAdmin) {
        const usersData = await getAdminUsers();
        setOrganizations(currentOrganizationOption);
        setUsers(usersData);
        return;
      }

      if (isTeamManager) {
        setOrganizations(currentOrganizationOption);
        setUsers([]);
        return;
      }

      setOrganizations([]);
      setUsers([]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load teams."));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [role, currentOrganizationId, currentOrganizationOption]);

  useEffect(() => {
    if (!memberForm.userId) {
      return;
    }

    const selectedUser = availableMembers.find(
      (appUser) => String(appUser.id) === memberForm.userId
    );

    if (!selectedUser) {
      return;
    }

    const nextRole = getDefaultMembershipRole(selectedUser);
    setMemberForm((previousForm) =>
      previousForm.role === nextRole
        ? previousForm
        : {
            ...previousForm,
            role: nextRole,
          }
    );
  }, [availableMembers, memberForm.userId]);

  const openCreateModal = (): void => {
    const defaultOrganization =
      visibleOrganizations.length === 1 ? visibleOrganizations[0].id : "";

    setEditingTeam(null);
    setForm({
      ...initialForm,
      organization: defaultOrganization,
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsModalOpen(true);
  };

  const openMembersModal = async (team: Team): Promise<void> => {
    setSelectedTeam(team);
    setTeamMembers([]);
    setMemberForm({
      userId: "",
      role: "tester",
      isPrimary: false,
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsMembersModalOpen(true);
    await loadMembersForTeam(team.id);
  };

  const openEditModal = (team: Team): void => {
    setEditingTeam(team);
    setForm({
      organization: team.organization,
      name: team.name,
      manager: team.manager ?? null,
      ai_provider: team.ai_provider ?? null,
      ai_api_key: null,
      ai_model: team.ai_model ?? "",
      monthly_token_budget: team.monthly_token_budget,
      jira_base_url: team.jira_base_url ?? "",
      jira_project_key: team.jira_project_key ?? "",
      github_org: team.github_org ?? "",
      github_repo: team.github_repo ?? "",
      jenkins_url: team.jenkins_url ?? "",
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsModalOpen(true);
  };

  const closeModal = (): void => {
    setIsModalOpen(false);
    setEditingTeam(null);
    setForm(initialForm);
  };

  const closeMembersModal = (): void => {
    setIsMembersModalOpen(false);
    setSelectedTeam(null);
    setTeamMembers([]);
    setMemberForm({
      userId: "",
      role: "tester",
      isPrimary: false,
    });
  };

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      if (editingTeam) {
        const payload: TeamUpdatePayload = {
          organization: form.organization,
          name: form.name,
          manager: form.manager ?? null,
          ai_provider: form.ai_provider ?? null,
          ai_api_key: form.ai_api_key?.trim() ? form.ai_api_key.trim() : null,
          ai_model: form.ai_model ?? "",
          monthly_token_budget: form.monthly_token_budget ?? DEFAULT_TOKEN_BUDGET,
          jira_base_url: form.jira_base_url?.trim() || null,
          jira_project_key: form.jira_project_key?.trim() || null,
          github_org: form.github_org?.trim() || null,
          github_repo: form.github_repo?.trim() || null,
          jenkins_url: form.jenkins_url?.trim() || null,
        };

        await updateTeam(editingTeam.id, payload);
        setSuccessMessage("Team updated successfully.");
      } else {
        const payload: TeamCreatePayload = {
          name: form.name.trim(),
          manager: form.manager ?? undefined,
        };

        if (form.organization) {
          payload.organization = form.organization;
        }

        if (form.ai_provider !== null && form.ai_provider !== undefined) {
          payload.ai_provider = form.ai_provider;
        }

        if (form.ai_api_key?.trim()) {
          payload.ai_api_key = form.ai_api_key.trim();
        }

        if (form.ai_model?.trim()) {
          payload.ai_model = form.ai_model.trim();
        }

        if (
          form.monthly_token_budget !== undefined &&
          form.monthly_token_budget !== DEFAULT_TOKEN_BUDGET
        ) {
          payload.monthly_token_budget = form.monthly_token_budget;
        }

        if (form.jira_base_url?.trim()) {
          payload.jira_base_url = form.jira_base_url.trim();
        }

        if (form.jira_project_key?.trim()) {
          payload.jira_project_key = form.jira_project_key.trim();
        }

        if (form.github_org?.trim()) {
          payload.github_org = form.github_org.trim();
        }

        if (form.github_repo?.trim()) {
          payload.github_repo = form.github_repo.trim();
        }

        if (form.jenkins_url?.trim()) {
          payload.jenkins_url = form.jenkins_url.trim();
        }

        await createTeam(payload);
        setSuccessMessage("Team created successfully.");
      }

      await loadData();
      closeModal();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to save team."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (teamId: string): Promise<void> => {
    const confirmed = globalThis.confirm(
      "Are you sure you want to delete this team?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingTeamId(teamId);
      setErrorMessage("");
      setSuccessMessage("");

      await deleteTeam(teamId);
      setSuccessMessage("Team deleted successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete team."));
    } finally {
      setDeletingTeamId(null);
    }
  };

  const handleAddMember = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    if (!selectedTeam || !memberForm.userId) {
      return;
    }

    try {
      setIsMemberSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      await addTeamMember(selectedTeam.id, {
        user: Number(memberForm.userId),
        role: memberForm.role,
        is_primary: memberForm.isPrimary,
      });

      setSuccessMessage("Team member added successfully.");
      setMemberForm({
        userId: "",
        role: "tester",
        isPrimary: false,
      });
      await Promise.all([loadData(), loadMembersForTeam(selectedTeam.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to add team member."));
    } finally {
      setIsMemberSaving(false);
    }
  };

  const handleMemberRoleChange = async (
    member: TeamMember,
    nextRole: TeamMembershipRole
  ): Promise<void> => {
    if (!selectedTeam || member.role === nextRole) {
      return;
    }

    try {
      setUpdatingMemberId(member.id);
      setErrorMessage("");
      setSuccessMessage("");

      await updateTeamMember(selectedTeam.id, member.id, {
        role: nextRole,
      });

      setSuccessMessage("Team member updated successfully.");
      await Promise.all([loadData(), loadMembersForTeam(selectedTeam.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update team member."));
    } finally {
      setUpdatingMemberId(null);
    }
  };

  const handleMakePrimary = async (member: TeamMember): Promise<void> => {
    if (!selectedTeam || member.is_primary) {
      return;
    }

    try {
      setUpdatingMemberId(member.id);
      setErrorMessage("");
      setSuccessMessage("");

      await updateTeamMember(selectedTeam.id, member.id, {
        is_primary: true,
      });

      setSuccessMessage("Primary team updated successfully.");
      await Promise.all([loadData(), loadMembersForTeam(selectedTeam.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update the primary team."));
    } finally {
      setUpdatingMemberId(null);
    }
  };

  const handleRemoveMember = async (member: TeamMember): Promise<void> => {
    if (!selectedTeam) {
      return;
    }

    const confirmed = globalThis.confirm(
      `Remove ${member.full_name} from ${selectedTeam.name}?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingMemberId(member.id);
      setErrorMessage("");
      setSuccessMessage("");

      await removeTeamMember(selectedTeam.id, member.id);
      setSuccessMessage("Team member removed successfully.");
      await Promise.all([loadData(), loadMembersForTeam(selectedTeam.id)]);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to remove team member."));
    } finally {
      setDeletingMemberId(null);
    }
  };

  const canManageMember = (member: TeamMember): boolean => {
    if (isPlatformOwner || isOrgAdmin) {
      return member.user_role !== "platform_owner" && member.user_role !== "org_admin";
    }

    if (isTeamManager) {
      return member.user_role === "tester" || member.user_role === "viewer";
    }

    return false;
  };

  const canSetPrimaryMember = (member: TeamMember): boolean => {
    return (
      (isPlatformOwner || isOrgAdmin) &&
      member.user_role !== "platform_owner" &&
      member.user_role !== "org_admin"
    );
  };

  const getRoleOptionsForMember = (): Array<{
    value: TeamMembershipRole;
    label: string;
  }> => {
    if (isTeamManager) {
      return TEAM_MANAGER_ROLE_OPTIONS;
    }

    return ALL_MEMBERSHIP_ROLE_OPTIONS;
  };

  let teamsContent: ReactNode;

  if (isLoading) {
    teamsContent = (
      <div className="flex min-h-[220px] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  } else if (visibleTeams.length === 0) {
    teamsContent = (
      <div className="p-6 text-sm text-muted">No teams found.</div>
    );
  } else {
    teamsContent = (
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-bg">
          <tr>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Team
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Organisation
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Manager
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Members
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              AI Provider
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              AI Model
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Actions
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-border">
          {visibleTeams.map((team) => {
            const isDeletingThisTeam = deletingTeamId === team.id;

            return (
              <tr key={team.id} className="transition hover:bg-bg">
                <td className="px-6 py-4 text-sm font-medium text-text">
                  {team.name}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {team.organization_name}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {team.manager_name ?? "-"}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {team.member_names.length > 0
                    ? team.member_names.join(", ")
                    : "-"}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {team.ai_provider_name ?? "-"}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {team.ai_model ?? "-"}
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  {canManageTeams ? (
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="secondary"
                        size="md"
                        onClick={() => void openMembersModal(team)}
                      >
                        Members
                      </Button>
                      <Button
                        variant="secondary"
                        size="md"
                        onClick={() => openEditModal(team)}
                      >
                        Edit
                      </Button>
                      {(isPlatformOwner || isOrgAdmin) && (
                        <Button
                          variant="danger"
                          size="md"
                          onClick={() => handleDelete(team.id)}
                          isLoading={isDeletingThisTeam}
                          loadingText="Deleting..."
                        >
                          Delete
                        </Button>
                      )}
                    </div>
                  ) : (
                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => void openMembersModal(team)}
                    >
                      Members
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

  const modalTitle = editingTeam ? "Edit Team" : "Create Team";
  const submitLabel = editingTeam ? "Update" : "Create";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Badge variant="tag">{isTeamManager ? "Manager workspace" : "Team workspace"}</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text">
            {isTeamManager ? "My Teams" : "Teams"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            {isTeamManager
              ? "Review your teams and manage their AI and integration settings."
              : "Manage teams and team-level configuration."}
          </p>
        </div>

        {(isPlatformOwner || isOrgAdmin) && (
          <Button onClick={openCreateModal}>New Team</Button>
        )}
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
        {teamsContent}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title={modalTitle}
        size="lg"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormSelect
            id="team-organization"
            label="Organisation"
            value={form.organization}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                organization: event.target.value,
                manager: null,
              }))
            }
            options={organizationOptions}
            placeholder="Select organisation"
            required={isPlatformOwner}
            disabled={!isPlatformOwner || visibleOrganizations.length === 1}
          />

          <FormInput
            id="team-name"
            label="Team name"
            type="text"
            value={form.name}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                name: event.target.value,
              }))
            }
            required
            disabled={isTeamManager}
          />

          <FormSelect
            id="team-manager"
            label="Manager"
            value={form.manager === null ? "" : String(form.manager)}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                manager: event.target.value
                  ? Number(event.target.value)
                  : null,
              }))
            }
            options={managerOptions}
            placeholder="Select manager"
            required
            disabled={isTeamManager}
          />

          <FormInput
            id="team-ai-api-key"
            label="AI API key"
            type="password"
            value={form.ai_api_key ?? ""}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                ai_api_key: event.target.value,
              }))
            }
            placeholder={
              editingTeam?.has_ai_api_key
                ? "Enter a new key to replace the current one"
                : "Enter AI API key"
            }
          />

          <div className="grid gap-4 md:grid-cols-2">
            <FormInput
              id="team-ai-provider"
              label="AI Provider ID"
              type="number"
              value={form.ai_provider === null || form.ai_provider === undefined ? "" : String(form.ai_provider)}
              onChange={(event) =>
                setForm((previousForm) => ({
                  ...previousForm,
                  ai_provider: event.target.value
                    ? Number(event.target.value)
                    : null,
                }))
              }
              placeholder="Provider ID"
            />

            <FormInput
              id="team-ai-model"
              label="AI Model"
              type="text"
              value={form.ai_model ?? ""}
              onChange={(event) =>
                setForm((previousForm) => ({
                  ...previousForm,
                  ai_model: event.target.value,
                }))
              }
              placeholder="gpt-4o-mini"
            />
          </div>

          <FormInput
            id="team-budget"
            label="Monthly token budget"
            type="number"
            min={0}
            value={String(form.monthly_token_budget ?? DEFAULT_TOKEN_BUDGET)}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                monthly_token_budget: Number(event.target.value),
              }))
            }
          />

          <div className="grid gap-4 md:grid-cols-2">
            <FormInput
              id="team-jira-url"
              label="Jira base URL"
              type="text"
              value={form.jira_base_url ?? ""}
              onChange={(event) =>
                setForm((previousForm) => ({
                  ...previousForm,
                  jira_base_url: event.target.value,
                }))
              }
            />

            <FormInput
              id="team-jira-key"
              label="Jira project key"
              type="text"
              value={form.jira_project_key ?? ""}
              onChange={(event) =>
                setForm((previousForm) => ({
                  ...previousForm,
                  jira_project_key: event.target.value,
                }))
              }
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <FormInput
              id="team-github-org"
              label="GitHub org"
              type="text"
              value={form.github_org ?? ""}
              onChange={(event) =>
                setForm((previousForm) => ({
                  ...previousForm,
                  github_org: event.target.value,
                }))
              }
            />

            <FormInput
              id="team-github-repo"
              label="GitHub repo"
              type="text"
              value={form.github_repo ?? ""}
              onChange={(event) =>
                setForm((previousForm) => ({
                  ...previousForm,
                  github_repo: event.target.value,
                }))
              }
            />
          </div>

          <FormInput
            id="team-jenkins-url"
            label="Jenkins URL"
            type="text"
            value={form.jenkins_url ?? ""}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                jenkins_url: event.target.value,
              }))
            }
          />

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={closeModal}>
              Cancel
            </Button>

            <Button
              type="submit"
              isLoading={isSaving}
              loadingText="Saving..."
            >
              {submitLabel}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isMembersModalOpen}
        onClose={closeMembersModal}
        title={selectedTeam ? `${selectedTeam.name} Members` : "Team Members"}
        size="xl"
      >
        <div className="space-y-6">
          {canAddMembers && selectedTeam ? (
            <form
              onSubmit={handleAddMember}
              className="rounded-[28px] border border-border bg-bg p-5"
            >
              <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
                <FormSelect
                  id="team-member-user"
                  label="User"
                  value={memberForm.userId}
                  onChange={(event) =>
                    setMemberForm((previousForm) => ({
                      ...previousForm,
                      userId: event.target.value,
                    }))
                  }
                  options={memberOptions}
                  placeholder="Select user"
                  required
                />

                <FormSelect
                  id="team-member-role"
                  label="Team role"
                  value={memberForm.role}
                  onChange={(event) =>
                    setMemberForm((previousForm) => ({
                      ...previousForm,
                      role: event.target.value as TeamMembershipRole,
                    }))
                  }
                  options={ALL_MEMBERSHIP_ROLE_OPTIONS}
                  required
                />
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-sm text-text">
                  <input
                    type="checkbox"
                    checked={memberForm.isPrimary}
                    onChange={(event) =>
                      setMemberForm((previousForm) => ({
                        ...previousForm,
                        isPrimary: event.target.checked,
                      }))
                    }
                    className="h-4 w-4"
                  />
                  Make this the user&apos;s primary team
                </label>

                <Button
                  type="submit"
                  isLoading={isMemberSaving}
                  loadingText="Adding..."
                  disabled={memberOptions.length === 0}
                >
                  Add Member
                </Button>
              </div>

              {memberOptions.length === 0 ? (
                <p className="mt-3 text-sm text-muted">
                  All eligible users in this organisation are already assigned to this team.
                </p>
              ) : null}
            </form>
          ) : null}

          {isMembersLoading ? (
            <div className="flex min-h-[180px] items-center justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : teamMembers.length === 0 ? (
            <div className="rounded-[28px] border border-dashed border-border bg-surface p-6 text-sm text-muted">
              No members found for this team.
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
                      Team Role
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Primary
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      Actions
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-border">
                  {teamMembers.map((member) => {
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
                          {canManageMember(member) ? (
                            <select
                              value={member.role}
                              onChange={(event) =>
                                void handleMemberRoleChange(
                                  member,
                                  event.target.value as TeamMembershipRole
                                )
                              }
                              disabled={isBusy}
                              className="rounded-2xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none transition focus-visible:ring-4 focus-visible:ring-primary-light/20"
                            >
                              {getRoleOptionsForMember().map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          ) : (
                            member.role
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted">
                          {member.is_primary ? (
                            <span className="rounded-full bg-primary px-3 py-1 text-xs font-semibold text-white">
                              Primary
                            </span>
                          ) : canSetPrimaryMember(member) ? (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => void handleMakePrimary(member)}
                              isLoading={isUpdatingThisMember}
                              loadingText="Saving..."
                            >
                              Make Primary
                            </Button>
                          ) : (
                            "-"
                          )}
                        </td>
                        <td className="px-6 py-4 text-right text-sm">
                          {canManageMember(member) ? (
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => void handleRemoveMember(member)}
                              isLoading={isDeletingThisMember}
                              loadingText="Removing..."
                            >
                              Remove
                            </Button>
                          ) : <span className="text-muted">View only</span>}
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
