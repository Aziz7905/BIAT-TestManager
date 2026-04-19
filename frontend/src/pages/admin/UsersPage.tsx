import { useEffect, useMemo, useState } from "react";
import AppLayout from "../../components/layout/AppLayout";
import { useAuthStore } from "../../store/authStore";
import {
  Badge,
  Button,
  ErrorMessage,
  Input,
  Modal,
  PageHeader,
  PaginationControls,
  Spinner,
} from "../../components/ui";
import {
  createUser,
  deleteUser,
  getUsersPage,
  updateUser,
} from "../../api/accounts/users";
import { getAllTeams } from "../../api/accounts/teams";
import type {
  AdminUser,
  CreateUserPayload,
  PaginatedResponse,
  Team,
  TeamMembershipSummary,
  TeamMembershipRole,
  UpdateUserPayload,
} from "../../types/accounts";

const ORG_ROLE_OPTIONS = [
  { value: "member", label: "Member" },
  { value: "org_admin", label: "Org Admin" },
];

const TEAM_ROLE_OPTIONS = [
  { value: "tester", label: "Tester" },
  { value: "viewer", label: "Viewer" },
  { value: "manager", label: "Manager" },
];

const ROLE_BADGE: Record<string, "purple" | "blue" | "slate"> = {
  platform_owner: "purple",
  org_admin: "blue",
  member: "slate",
};

interface UserFormState {
  first_name: string;
  last_name: string;
  password: string;
  team: string;
  team_membership_role: TeamMembershipRole;
  organization_role: string;
  is_staff: boolean;
}

const emptyForm: UserFormState = {
  first_name: "",
  last_name: "",
  password: "",
  team: "",
  team_membership_role: "tester",
  organization_role: "member",
  is_staff: false,
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getPrimaryMembership(user: AdminUser): TeamMembershipSummary | null {
  const memberships = user.profile?.team_memberships ?? [];
  return memberships.find((membership) => membership.is_primary) ?? memberships[0] ?? null;
}

function extractError(err: unknown): string {
  if (typeof err === "object" && err !== null && "response" in err) {
    const response = (err as { response?: { data?: Record<string, unknown> } }).response;
    const data = response?.data;
    if (data) {
      if (typeof data.detail === "string") {
        return data.detail;
      }
      const firstKey = Object.keys(data)[0];
      const firstValue = data[firstKey];
      if (Array.isArray(firstValue)) {
        return `${firstKey}: ${String(firstValue[0])}`;
      }
      if (typeof firstValue === "string") {
        return `${firstKey}: ${firstValue}`;
      }
    }
  }
  return "An error occurred. Please try again.";
}

function UserForm({
  form,
  setField,
  teams,
  error,
  isEdit,
  isPlatformOwner,
}: {
  form: UserFormState;
  setField: <K extends keyof UserFormState>(key: K, value: UserFormState[K]) => void;
  teams: Team[];
  error: string;
  isEdit: boolean;
  isPlatformOwner: boolean;
}) {
  return (
    <div className="space-y-4">
      {error && <ErrorMessage message={error} />}
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          id="users-first-name"
          label="First name"
          value={form.first_name}
          onChange={(event) => setField("first_name", event.target.value)}
          required
        />
        <Input
          id="users-last-name"
          label="Last name"
          value={form.last_name}
          onChange={(event) => setField("last_name", event.target.value)}
          required
        />
      </div>

      <Input
        id="users-password"
        label={isEdit ? "New password (leave blank to keep current)" : "Password"}
        type="password"
        value={form.password}
        onChange={(event) => setField("password", event.target.value)}
        required={!isEdit}
      />

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700">Primary team</label>
        <select
          value={form.team}
          onChange={(event) => setField("team", event.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
        >
          <option value="">No primary team</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
      </div>

      {form.team && (
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Team role</label>
          <select
            value={form.team_membership_role}
            onChange={(event) =>
              setField("team_membership_role", event.target.value as TeamMembershipRole)
            }
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
          >
            {TEAM_ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      )}

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700">Organization role</label>
        <select
          value={form.organization_role}
          onChange={(event) => setField("organization_role", event.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
        >
          {ORG_ROLE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {isPlatformOwner && (
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={form.is_staff}
            onChange={(event) => setField("is_staff", event.target.checked)}
            className="h-4 w-4 rounded border-slate-300 accent-blue-600"
          />
          <span className="text-sm text-slate-700">Staff (Django admin access)</span>
        </label>
      )}
    </div>
  );
}

export default function UsersPage() {
  const isPlatformOwner = useAuthStore((s) => s.user?.profile?.organization_role === "platform_owner");
  const [usersPage, setUsersPage] = useState<PaginatedResponse<AdminUser> | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingTeams, setLoadingTeams] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<AdminUser | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  async function loadUsers(targetPage: number) {
    setLoading(true);
    try {
      const response = await getUsersPage(targetPage);
      setUsersPage(response);
    } catch {
      setError("Failed to load users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadUsers(page);
  }, [page]);

  useEffect(() => {
    setLoadingTeams(true);
    getAllTeams()
      .then(setTeams)
      .catch(() => setError("Failed to load teams."))
      .finally(() => setLoadingTeams(false));
  }, []);

  const users = usersPage?.results ?? [];
  const filteredUsers = useMemo(() => {
    const query = search.toLowerCase().trim();
    if (!query) {
      return users;
    }

    return users.filter((user) => {
      const fullName = `${user.first_name} ${user.last_name}`.toLowerCase();
      return user.email.toLowerCase().includes(query) || fullName.includes(query);
    });
  }, [search, users]);

  function openCreate() {
    setForm(emptyForm);
    setFormError("");
    setCreateOpen(true);
  }

  function openEdit(user: AdminUser) {
    const primaryMembership = getPrimaryMembership(user);
    setForm({
      first_name: user.first_name,
      last_name: user.last_name,
      password: "",
      team: user.profile?.team ?? "",
      team_membership_role: primaryMembership?.role ?? "tester",
      organization_role: user.profile?.organization_role ?? "member",
      is_staff: user.is_staff,
    });
    setFormError("");
    setEditUser(user);
  }

  function setField<K extends keyof UserFormState>(key: K, value: UserFormState[K]) {
    setForm((currentForm) => ({ ...currentForm, [key]: value }));
  }

  async function handleCreate() {
    setFormError("");
    setSaving(true);

    try {
      const payload: CreateUserPayload = {
        first_name: form.first_name,
        last_name: form.last_name,
        password: form.password,
        organization_role: form.organization_role as CreateUserPayload["organization_role"],
        is_staff: form.is_staff,
      };

      if (form.team) {
        payload.team = form.team;
        payload.team_membership_role = form.team_membership_role;
      }

      await createUser(payload);
      setCreateOpen(false);
      if (page === 1) {
        await loadUsers(1);
      } else {
        setPage(1);
      }
    } catch (err) {
      setFormError(extractError(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate() {
    if (!editUser) {
      return;
    }

    setFormError("");
    setSaving(true);

    try {
      const payload: UpdateUserPayload = {
        first_name: form.first_name,
        last_name: form.last_name,
        organization_role: form.organization_role as UpdateUserPayload["organization_role"],
        is_staff: form.is_staff,
        team: form.team || null,
      };

      if (form.password) {
        payload.password = form.password;
      }

      if (form.team) {
        payload.team_membership_role = form.team_membership_role;
      }

      await updateUser(editUser.id, payload);
      setEditUser(null);
      await loadUsers(page);
    } catch (err) {
      setFormError(extractError(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) {
      return;
    }

    setSaving(true);
    try {
      await deleteUser(deleteTarget.id);
      setDeleteTarget(null);
      if (users.length === 1 && page > 1) {
        setPage(page - 1);
      } else {
        await loadUsers(page);
      }
    } catch {
      setError("Failed to delete user.");
      setDeleteTarget(null);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-6xl space-y-6">
          <PageHeader
            title="Users"
            subtitle={`${usersPage?.count ?? 0} users in the visible admin scope`}
            actions={<Button onClick={openCreate}>New user</Button>}
          />

          {error && <ErrorMessage message={error} onDismiss={() => setError("")} />}

          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <Input
                id="user-search"
                label="Filter current page"
                placeholder="Search by name or email"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>

            {loading ? (
              <div className="flex min-h-[280px] items-center justify-center">
                <Spinner size="lg" />
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[780px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        <th className="px-5 py-3">Name</th>
                        <th className="px-5 py-3">Email / Username</th>
                        <th className="px-5 py-3">Organization role</th>
                        <th className="px-5 py-3">Primary team</th>
                        <th className="px-5 py-3">Joined</th>
                        <th className="px-5 py-3" />
                      </tr>
                    </thead>
                    <tbody>
                      {filteredUsers.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-5 py-10 text-center text-slate-400">
                            {search ? "No users match the current page filter." : "No users found."}
                          </td>
                        </tr>
                      )}
                      {filteredUsers.map((user) => {
                        const primaryMembership = getPrimaryMembership(user);
                        return (
                          <tr key={user.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/50">
                            <td className="px-5 py-3">
                              <div className="flex items-center gap-3">
                                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">
                                  {user.first_name[0]}
                                  {user.last_name[0]}
                                </span>
                                <div className="min-w-0">
                                  <p className="truncate font-medium text-slate-900">
                                    {user.first_name} {user.last_name}
                                  </p>
                                  {user.is_staff && (
                                    <p className="text-xs text-slate-400">Staff account</p>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td className="px-5 py-3 text-slate-500">
                              <p>{user.email}</p>
                              <p className="text-xs text-slate-400">{user.username}</p>
                            </td>
                            <td className="px-5 py-3">
                              <Badge
                                label={user.profile?.organization_role?.replaceAll("_", " ") ?? "Unknown"}
                                color={ROLE_BADGE[user.profile?.organization_role ?? "member"] ?? "slate"}
                              />
                            </td>
                            <td className="px-5 py-3 text-slate-500">
                              <p>{user.profile?.team_name ?? "Not assigned"}</p>
                              {primaryMembership && (
                                <p className="text-xs text-slate-400">
                                  {primaryMembership.role.replaceAll("_", " ")}
                                </p>
                              )}
                            </td>
                            <td className="px-5 py-3 text-slate-400">{formatDate(user.date_joined)}</td>
                            <td className="px-5 py-3">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={() => openEdit(user)}
                                  className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
                                >
                                  Edit
                                </button>
                                {user.profile?.organization_role !== "platform_owner" && (
                                  <button
                                    onClick={() => setDeleteTarget(user)}
                                    className="rounded-md px-3 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50"
                                  >
                                    Delete
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  page={page}
                  totalCount={usersPage?.count ?? 0}
                  hasNext={Boolean(usersPage?.next)}
                  hasPrevious={Boolean(usersPage?.previous)}
                  itemLabel="users"
                  onNext={() => setPage((currentPage) => currentPage + 1)}
                  onPrevious={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
                />
              </>
            )}
          </div>
        </div>
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New user">
        <UserForm
          form={form}
          setField={setField}
          teams={teams}
          error={formError || (loadingTeams ? "Loading teams..." : "")}
          isEdit={false}
          isPlatformOwner={isPlatformOwner}
        />
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setCreateOpen(false)}>
            Cancel
          </Button>
          <Button isLoading={saving} loadingText="Creating..." onClick={handleCreate}>
            Create user
          </Button>
        </div>
      </Modal>

      <Modal open={Boolean(editUser)} onClose={() => setEditUser(null)} title="Edit user">
        <UserForm form={form} setField={setField} teams={teams} error={formError} isEdit isPlatformOwner={isPlatformOwner} />
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setEditUser(null)}>
            Cancel
          </Button>
          <Button isLoading={saving} loadingText="Saving..." onClick={handleUpdate}>
            Save changes
          </Button>
        </div>
      </Modal>

      <Modal open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} title="Delete user">
        <p className="text-sm text-slate-600">
          Are you sure you want to delete{" "}
          <span className="font-semibold">
            {deleteTarget?.first_name} {deleteTarget?.last_name}
          </span>
          ? This cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button variant="danger" isLoading={saving} loadingText="Deleting..." onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </AppLayout>
  );
}
