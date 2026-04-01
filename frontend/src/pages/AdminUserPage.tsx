import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  createAdminUser,
  deleteAdminUser,
  getAdminUsers,
  updateAdminUser,
} from "../api/accounts/users";
import { getTeams } from "../api/accounts/teams";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { FormSelect } from "../components/FormSelect";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import { useAuthStore } from "../store/authStore";
import type {
  AdminCreateUserPayload,
  AdminUpdateUserPayload,
  AdminUser,
  Team,
  UserProfileRole,
} from "../types/accounts";

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as {
      response?: { data?: { detail?: string; error?: string } };
    }).response;

    return response?.data?.detail || response?.data?.error || fallback;
  }

  return fallback;
}

const ROLE_OPTIONS: UserProfileRole[] = [
  "platform_owner",
  "org_admin",
  "team_manager",
  "tester",
  "viewer",
];

const initialCreateForm: AdminCreateUserPayload = {
  first_name: "",
  last_name: "",
  password: "",
  team: "",
  is_staff: false,
};

const initialEditForm: AdminUpdateUserPayload = {
  first_name: "",
  last_name: "",
  team: "",
  role: "tester",
  is_staff: false,
  password: "",
};

export default function AdminUserPage() {
  const { user } = useAuthStore();
  const role = user?.profile?.role;
  const isPlatformOwner = role === "platform_owner";
  const isOrgAdmin = role === "org_admin";
  const isTeamManager = role === "team_manager";
  const canCreateUsers = isPlatformOwner || isOrgAdmin;
  const canEditUsers = isPlatformOwner || isOrgAdmin || isTeamManager;

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);

  const [createForm, setCreateForm] =
    useState<AdminCreateUserPayload>(initialCreateForm);
  const [editForm, setEditForm] =
    useState<AdminUpdateUserPayload>(initialEditForm);

  const currentOrganizationId = user?.profile?.organization;
  const managedTeamIds = useMemo(
    () =>
      user?.profile?.team_memberships
        ?.filter(
          (membership) => membership.role === "manager" && membership.is_active
        )
        .map((membership) => membership.team) ?? [],
    [user?.profile?.team_memberships]
  );

  const visibleTeams = useMemo(() => {
    if (isPlatformOwner) {
      return teams;
    }

    if (isTeamManager) {
      return teams.filter((team) => managedTeamIds.includes(team.id));
    }

    return teams.filter(
      (team) => team.organization === currentOrganizationId
    );
  }, [teams, isPlatformOwner, isTeamManager, currentOrganizationId, managedTeamIds]);

  const visibleUsers = useMemo(() => {
    if (isPlatformOwner) {
      return users;
    }

    if (isTeamManager) {
      return users.filter(
        (appUser) =>
          appUser.profile?.team_memberships?.some((membership) =>
            managedTeamIds.includes(membership.team)
          ) ?? false
      );
    }

    return users.filter(
      (appUser) => appUser.profile?.organization === currentOrganizationId
    );
  }, [users, isPlatformOwner, isTeamManager, currentOrganizationId, managedTeamIds]);

  const allowedCreateRoles: UserProfileRole[] = isPlatformOwner
    ? ROLE_OPTIONS
    : ["team_manager", "tester", "viewer"];

  const allowedEditRoles: UserProfileRole[] = isPlatformOwner
    ? ROLE_OPTIONS
    : isTeamManager
      ? ["tester", "viewer"]
    : ["org_admin", "team_manager", "tester", "viewer"];

  const createRoleOptions = allowedCreateRoles.map((allowedRole) => ({
    value: allowedRole,
    label: allowedRole,
  }));

  const editRoleOptions = allowedEditRoles.map((allowedRole) => ({
    value: allowedRole,
    label: allowedRole,
  }));

  const teamOptions = visibleTeams.map((team) => ({
    value: team.id,
    label: team.name,
  }));

  const canManageUserRecord = (appUser: AdminUser): boolean => {
    const userRole = appUser.profile?.role;
    const userTeamIds =
      appUser.profile?.team_memberships?.map((membership) => membership.team) ?? [];

    if (isPlatformOwner || isOrgAdmin) {
      return true;
    }

    if (isTeamManager) {
      return (
        userTeamIds.some((teamId) => managedTeamIds.includes(teamId)) &&
        (userRole === "tester" || userRole === "viewer")
      );
    }

    return false;
  };

  const loadData = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const [usersData, teamsData] = await Promise.all([
        getAdminUsers(),
        getTeams(),
      ]);

      setUsers(usersData);
      setTeams(teamsData);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to load users."));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const openCreateModal = (): void => {
    const defaultTeam = visibleTeams.length === 1 ? visibleTeams[0].id : "";

    setEditingUser(null);
    setCreateForm({
      ...initialCreateForm,
      team: defaultTeam,
      is_staff: false,
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsModalOpen(true);
  };

  const openEditModal = (appUser: AdminUser): void => {
    setEditingUser(appUser);
    setEditForm({
      first_name: appUser.first_name,
      last_name: appUser.last_name,
      team: appUser.profile?.team ?? "",
      role: appUser.profile?.role ?? "tester",
      is_staff: appUser.is_staff,
      password: "",
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsModalOpen(true);
  };

  const closeModal = (): void => {
    setIsModalOpen(false);
    setEditingUser(null);
    setCreateForm(initialCreateForm);
    setEditForm(initialEditForm);
  };

  const handleCreateSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    const payload: AdminCreateUserPayload = {
      first_name: createForm.first_name.trim(),
      last_name: createForm.last_name.trim(),
      password: createForm.password,
      is_staff: createForm.is_staff,
    };

    if (createForm.team) {
      payload.team = createForm.team;
    }

    if (createForm.role) {
      payload.role = createForm.role;
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      await createAdminUser(payload);
      setSuccessMessage("User created successfully.");
      await loadData();
      closeModal();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to create user."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleEditSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    if (!editingUser) {
      return;
    }

    const payload: AdminUpdateUserPayload = {
      first_name: editForm.first_name?.trim() || undefined,
      last_name: editForm.last_name?.trim() || undefined,
      team: editForm.team || undefined,
      role: editForm.role,
      is_staff: editForm.is_staff,
    };

    if (editForm.password?.trim()) {
      payload.password = editForm.password.trim();
    }

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      await updateAdminUser(editingUser.id, payload);
      setSuccessMessage("User updated successfully.");
      await loadData();
      closeModal();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to update user."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (userId: number): Promise<void> => {
    const confirmed = globalThis.confirm(
      "Are you sure you want to delete this user?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingUserId(userId);
      setErrorMessage("");
      setSuccessMessage("");

      await deleteAdminUser(userId);
      setSuccessMessage("User deleted successfully.");
      await loadData();
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, "Failed to delete user."));
    } finally {
      setDeletingUserId(null);
    }
  };

  let usersContent: ReactNode;

  if (isLoading) {
    usersContent = (
      <div className="flex min-h-[220px] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  } else if (visibleUsers.length === 0) {
    usersContent = (
      <div className="p-6 text-sm text-gray-500">No users found.</div>
    );
  } else {
    usersContent = (
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Name
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Email
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Role
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Team
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
              Actions
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-gray-100">
          {visibleUsers.map((appUser) => {
            const teamNames = appUser.profile?.team_memberships?.map(
              (membership) => membership.team_name
            ) ?? [];
            const teamDisplay =
              teamNames.length > 0 ? Array.from(new Set(teamNames)).join(", ") : "-";
            const isDeletingThisUser = deletingUserId === appUser.id;

            return (
              <tr key={appUser.id}>
                <td className="px-6 py-4 text-sm text-gray-900">
                  {appUser.first_name} {appUser.last_name}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">
                  {appUser.email}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">
                  {appUser.profile?.role ?? "-"}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">
                  {teamDisplay}
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  {canEditUsers && canManageUserRecord(appUser) ? (
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="secondary"
                        size="md"
                        onClick={() => openEditModal(appUser)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="danger"
                        size="md"
                        onClick={() => handleDelete(appUser.id)}
                        isLoading={isDeletingThisUser}
                        loadingText="Deleting..."
                      >
                        Delete
                      </Button>
                    </div>
                  ) : (
                    <span className="text-gray-400">View only</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            {isTeamManager ? "Team Members" : "Users"}
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {isTeamManager
              ? "Review and manage the members assigned to your team."
              : "Manage users in your organisation."}
          </p>
        </div>

        {canCreateUsers ? <Button onClick={openCreateModal}>New User</Button> : null}
      </div>

      {successMessage ? (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
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

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        {usersContent}
      </div>

      <Modal
        isOpen={isModalOpen && !editingUser}
        onClose={closeModal}
        title="Create User"
        size="lg"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <FormInput
              id="create-first-name"
              label="First name"
              type="text"
              value={createForm.first_name}
              onChange={(event) =>
                setCreateForm((previousForm) => ({
                  ...previousForm,
                  first_name: event.target.value,
                }))
              }
              required
            />

            <FormInput
              id="create-last-name"
              label="Last name"
              type="text"
              value={createForm.last_name}
              onChange={(event) =>
                setCreateForm((previousForm) => ({
                  ...previousForm,
                  last_name: event.target.value,
                }))
              }
              required
            />
          </div>

          <FormInput
            id="create-password"
            label="Password"
            type="password"
            value={createForm.password}
            onChange={(event) =>
              setCreateForm((previousForm) => ({
                ...previousForm,
                password: event.target.value,
              }))
            }
            required
          />

          <FormSelect
            id="create-team"
            label="Team"
            value={createForm.team}
            onChange={(event) =>
              setCreateForm((previousForm) => ({
                ...previousForm,
                team: event.target.value,
              }))
            }
            options={teamOptions}
            placeholder="Select team"
          />

          <FormSelect
            id="create-role"
            label="Role"
            value={createForm.role ?? ""}
            onChange={(event) =>
              setCreateForm((previousForm) => ({
                ...previousForm,
                role: event.target.value
                  ? (event.target.value as UserProfileRole)
                  : undefined,
              }))
            }
            options={createRoleOptions}
            placeholder="Select role"
          />

          {isPlatformOwner ? (
            <div className="flex items-center gap-2">
              <input
                id="create-is-staff"
                type="checkbox"
                checked={createForm.is_staff ?? false}
                onChange={(event) =>
                  setCreateForm((previousForm) => ({
                    ...previousForm,
                    is_staff: event.target.checked,
                  }))
                }
                className="h-4 w-4"
              />
              <label
                htmlFor="create-is-staff"
                className="text-sm text-gray-700"
              >
                Django staff access
              </label>
            </div>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              type="submit"
              isLoading={isSaving}
              loadingText="Creating..."
            >
              Create
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isModalOpen && !!editingUser}
        onClose={closeModal}
        title="Edit User"
        size="lg"
      >
        <form onSubmit={handleEditSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <FormInput
              id="edit-first-name"
              label="First name"
              type="text"
              value={editForm.first_name ?? ""}
              onChange={(event) =>
                setEditForm((previousForm) => ({
                  ...previousForm,
                  first_name: event.target.value,
                }))
              }
              required
            />

            <FormInput
              id="edit-last-name"
              label="Last name"
              type="text"
              value={editForm.last_name ?? ""}
              onChange={(event) =>
                setEditForm((previousForm) => ({
                  ...previousForm,
                  last_name: event.target.value,
                }))
              }
              required
            />
          </div>

          <FormInput
            id="edit-email"
            label="Email"
            type="text"
            value={editingUser?.email ?? ""}
            disabled
          />

          <div className="grid gap-4 md:grid-cols-2">
            <FormSelect
              id="edit-team"
              label="Team"
              value={editForm.team ?? ""}
              onChange={(event) =>
                setEditForm((previousForm) => ({
                  ...previousForm,
                  team: event.target.value,
                }))
              }
              options={teamOptions}
              placeholder="Select team"
              required
              disabled={isTeamManager}
            />

            <FormSelect
              id="edit-role"
              label="Role"
              value={editForm.role ?? "tester"}
              onChange={(event) =>
                setEditForm((previousForm) => ({
                  ...previousForm,
                  role: event.target.value as UserProfileRole,
                }))
              }
              options={editRoleOptions}
              required
            />
          </div>

          <FormInput
            id="edit-password"
            label="New password"
            type="password"
            value={editForm.password ?? ""}
            onChange={(event) =>
              setEditForm((previousForm) => ({
                ...previousForm,
                password: event.target.value,
              }))
            }
            helperText="Leave empty to keep the current password."
          />

          {isPlatformOwner ? (
            <div className="flex items-center gap-2">
              <input
                id="edit-is-staff"
                type="checkbox"
                checked={editForm.is_staff ?? false}
                onChange={(event) =>
                  setEditForm((previousForm) => ({
                    ...previousForm,
                    is_staff: event.target.checked,
                  }))
                }
                className="h-4 w-4"
              />
              <label htmlFor="edit-is-staff" className="text-sm text-gray-700">
                Django staff access
              </label>
            </div>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              type="submit"
              isLoading={isSaving}
              loadingText="Saving..."
            >
              Update
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
