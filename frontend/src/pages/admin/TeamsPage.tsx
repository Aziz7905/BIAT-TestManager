import { useEffect, useMemo, useState } from "react";
import AppLayout from "../../components/layout/AppLayout";
import { useAuthStore } from "../../store/authStore";
import {
  Button,
  ErrorMessage,
  Input,
  Modal,
  PaginationControls,
  Spinner,
  UserPicker,
} from "../../components/ui";
import {
  addTeamMember,
  createTeam,
  deleteTeam,
  getTeamMembersPage,
  getTeamsPage,
  removeTeamMember,
  updateTeam,
  updateTeamMember,
} from "../../api/accounts/teams";
import { getAllUsers } from "../../api/accounts/users";
import type {
  AdminUser,
  CreateTeamPayload,
  PaginatedResponse,
  Team,
  TeamMember,
  TeamMembershipRole,
  UpdateTeamPayload,
} from "../../types/accounts";

const TEAM_ROLE_OPTIONS = [
  { value: "tester", label: "Tester" },
  { value: "viewer", label: "Viewer" },
  { value: "manager", label: "Manager" },
];

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
  return "An error occurred.";
}

function TeamCard({
  team,
  isSelected,
  isAdmin,
  onSelect,
  onDelete,
}: {
  team: Team;
  isSelected: boolean;
  isAdmin: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={[
        "cursor-pointer rounded-lg border bg-white p-4 shadow-sm transition",
        isSelected ? "border-blue-300 shadow-md" : "border-slate-200 hover:border-blue-200 hover:shadow-md",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-900">{team.name}</p>
          <p className="mt-0.5 text-xs text-slate-400">{team.organization_name}</p>
        </div>
        {team.has_ai_api_key && (
          <span className="shrink-0 rounded-full bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-700">
            AI
          </span>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
        <span>{team.member_count} members</span>
        <span className="truncate">{team.manager_name ?? "No manager"}</span>
      </div>

      <div className="mt-3 flex gap-2" onClick={(event) => event.stopPropagation()}>
        <button
          onClick={onSelect}
          className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
        >
          Manage
        </button>
        {isAdmin && (
          <button
            onClick={onDelete}
            className="rounded-md px-3 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

export default function TeamsPage() {
  const currentUser = useAuthStore((s) => s.user);
  const orgRole = currentUser?.profile?.organization_role;
  const isAdmin = orgRole === "platform_owner" || orgRole === "org_admin";

  const [teamsPage, setTeamsPage] = useState<PaginatedResponse<Team> | null>(null);
  const [teamsPageNumber, setTeamsPageNumber] = useState(1);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [membersPage, setMembersPage] = useState<PaginatedResponse<TeamMember> | null>(null);
  const [membersPageNumber, setMembersPageNumber] = useState(1);
  const [users, setUsers] = useState<AdminUser[]>([]);

  const [loadingTeams, setLoadingTeams] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [error, setError] = useState("");
  const [settingsError, setSettingsError] = useState("");
  const [memberError, setMemberError] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", manager: null as number | null });
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Team | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [editForm, setEditForm] = useState<UpdateTeamPayload>({});
  const [editAiKey, setEditAiKey] = useState("");
  const [savingSettings, setSavingSettings] = useState(false);

  const [addMemberUserId, setAddMemberUserId] = useState<number | null>(null);
  const [addMemberRole, setAddMemberRole] = useState<TeamMembershipRole>("tester");
  const [addingMember, setAddingMember] = useState(false);

  async function loadTeams(targetPage: number) {
    setLoadingTeams(true);
    try {
      const response = await getTeamsPage(targetPage);
      setTeamsPage(response);

      if (!selectedTeam && response.results[0]) {
        setSelectedTeam(response.results[0]);
      } else if (selectedTeam) {
        const matchingTeam = response.results.find((team) => team.id === selectedTeam.id);
        if (matchingTeam) {
          setSelectedTeam(matchingTeam);
        }
      }
    } catch {
      setError("Failed to load teams.");
    } finally {
      setLoadingTeams(false);
    }
  }

  useEffect(() => {
    void loadTeams(teamsPageNumber);
  }, [teamsPageNumber]);

  useEffect(() => {
    if (!isAdmin) {
      setLoadingUsers(false);
      return;
    }
    setLoadingUsers(true);
    getAllUsers()
      .then(setUsers)
      .catch(() => setError("Failed to load users."))
      .finally(() => setLoadingUsers(false));
  }, [isAdmin]);

  useEffect(() => {
    if (!selectedTeam) {
      setMembersPage(null);
      return;
    }

    setLoadingMembers(true);
    getTeamMembersPage(selectedTeam.id, membersPageNumber)
      .then(setMembersPage)
      .catch(() => setError("Failed to load team members."))
      .finally(() => setLoadingMembers(false));
  }, [membersPageNumber, selectedTeam]);

  useEffect(() => {
    if (!selectedTeam) {
      return;
    }

    setEditForm({
      name: selectedTeam.name,
      manager: selectedTeam.manager ?? undefined,
      ai_model: selectedTeam.ai_model,
      monthly_token_budget: selectedTeam.monthly_token_budget,
      jira_base_url: selectedTeam.jira_base_url ?? "",
      jira_project_key: selectedTeam.jira_project_key ?? "",
      github_org: selectedTeam.github_org ?? "",
      github_repo: selectedTeam.github_repo ?? "",
      jenkins_url: selectedTeam.jenkins_url ?? "",
    });
    setEditAiKey("");
    setSettingsError("");
    setMemberError("");
    setAddMemberUserId(null);
  }, [selectedTeam]);

  const availableUsers = useMemo(() => {
    const currentMemberIds = new Set((membersPage?.results ?? []).map((member) => member.user_id));
    return users.filter((user) => !currentMemberIds.has(user.id));
  }, [membersPage?.results, users]);

  function selectTeam(team: Team) {
    setSelectedTeam(team);
    setMembersPageNumber(1);
  }

  async function handleCreate() {
    if (!createForm.name || createForm.manager === null) {
      setCreateError("Name and manager are required.");
      return;
    }

    setCreating(true);
    setCreateError("");
    try {
      const payload: CreateTeamPayload = {
        name: createForm.name,
        manager: createForm.manager,
      };
      await createTeam(payload);
      setCreateOpen(false);
      setCreateForm({ name: "", manager: null });
      if (teamsPageNumber === 1) {
        await loadTeams(1);
      } else {
        setTeamsPageNumber(1);
      }
    } catch (err) {
      setCreateError(extractError(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveSettings() {
    if (!selectedTeam) {
      return;
    }

    setSavingSettings(true);
    setSettingsError("");
    try {
      const payload: UpdateTeamPayload = { ...editForm };
      if (editAiKey) {
        payload.ai_api_key = editAiKey;
      }
      const updatedTeam = await updateTeam(selectedTeam.id, payload);
      setSelectedTeam(updatedTeam);
      setEditAiKey("");
      setTeamsPage((currentPage) =>
        currentPage
          ? {
              ...currentPage,
              results: currentPage.results.map((team) =>
                team.id === updatedTeam.id ? updatedTeam : team
              ),
            }
          : currentPage
      );
    } catch (err) {
      setSettingsError(extractError(err));
    } finally {
      setSavingSettings(false);
    }
  }

  async function handleDeleteTeam() {
    if (!deleteTarget) {
      return;
    }

    setDeleting(true);
    try {
      await deleteTeam(deleteTarget.id);
      if (selectedTeam?.id === deleteTarget.id) {
        setSelectedTeam(null);
      }
      setDeleteTarget(null);
      if ((teamsPage?.results.length ?? 0) === 1 && teamsPageNumber > 1) {
        setTeamsPageNumber(teamsPageNumber - 1);
      } else {
        await loadTeams(teamsPageNumber);
      }
    } catch {
      setError("Failed to delete team.");
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  async function handleAddMember() {
    if (!selectedTeam || addMemberUserId === null) {
      return;
    }

    setAddingMember(true);
    setMemberError("");
    try {
      await addTeamMember(selectedTeam.id, {
        user: addMemberUserId,
        role: addMemberRole,
      });
      setAddMemberUserId(null);
      setAddMemberRole("tester");
      await loadTeams(teamsPageNumber);
      const refreshedMembers = await getTeamMembersPage(selectedTeam.id, 1);
      setMembersPage(refreshedMembers);
      setMembersPageNumber(1);
    } catch (err) {
      setMemberError(extractError(err));
    } finally {
      setAddingMember(false);
    }
  }

  async function handleUpdateMemberRole(member: TeamMember, role: TeamMembershipRole) {
    if (!selectedTeam) {
      return;
    }

    try {
      const updatedMember = await updateTeamMember(selectedTeam.id, member.id, { role });
      setMembersPage((currentPage) =>
        currentPage
          ? {
              ...currentPage,
              results: currentPage.results.map((currentMember) =>
                currentMember.id === updatedMember.id ? updatedMember : currentMember
              ),
            }
          : currentPage
      );
    } catch {
      setError("Failed to update member role.");
    }
  }

  async function handleRemoveMember(member: TeamMember) {
    if (!selectedTeam) {
      return;
    }

    try {
      await removeTeamMember(selectedTeam.id, member.id);
      await loadTeams(teamsPageNumber);
      if ((membersPage?.results.length ?? 0) === 1 && membersPageNumber > 1) {
        setMembersPageNumber(membersPageNumber - 1);
      } else {
        const refreshedPage = await getTeamMembersPage(selectedTeam.id, membersPageNumber);
        setMembersPage(refreshedPage);
      }
    } catch {
      setError("Failed to remove member.");
    }
  }

  return (
    <AppLayout>
      <div className="flex h-full overflow-hidden">
        <aside className="flex w-80 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
          <div className="border-b border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-base font-semibold text-slate-900">Teams</h1>
                <p className="text-xs text-slate-500">
                  {teamsPage?.count ?? 0} teams in your admin scope
                </p>
              </div>
              {isAdmin && (
                <Button
                  size="sm"
                  onClick={() => {
                    setCreateError("");
                    setCreateOpen(true);
                  }}
                >
                  New
                </Button>
              )}
            </div>
          </div>

          {error && <ErrorMessage message={error} onDismiss={() => setError("")} className="m-3" />}

          {loadingTeams ? (
            <div className="flex flex-1 items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : (
            <>
              <div className="flex-1 space-y-3 overflow-y-auto p-3">
                {(teamsPage?.results.length ?? 0) === 0 ? (
                  <p className="py-8 text-center text-sm text-slate-400">No teams available.</p>
                ) : (
                  teamsPage?.results.map((team) => (
                    <TeamCard
                      key={team.id}
                      team={team}
                      isSelected={selectedTeam?.id === team.id}
                      isAdmin={isAdmin}
                      onSelect={() => selectTeam(team)}
                      onDelete={() => isAdmin && setDeleteTarget(team)}
                    />
                  ))
                )}
              </div>

              <PaginationControls
                page={teamsPageNumber}
                totalCount={teamsPage?.count ?? 0}
                hasNext={Boolean(teamsPage?.next)}
                hasPrevious={Boolean(teamsPage?.previous)}
                itemLabel="teams"
                onNext={() => setTeamsPageNumber((currentPage) => currentPage + 1)}
                onPrevious={() => setTeamsPageNumber((currentPage) => Math.max(1, currentPage - 1))}
              />
            </>
          )}
        </aside>

        {selectedTeam ? (
          <main className="flex flex-1 flex-col overflow-hidden bg-white">
            <div className="border-b border-slate-200 px-6 py-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{selectedTeam.name}</h2>
                  <p className="text-sm text-slate-500">{selectedTeam.organization_name}</p>
                </div>
                <Button isLoading={savingSettings} loadingText="Saving..." onClick={handleSaveSettings}>
                  Save settings
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-6">
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_420px]">
                <div className="space-y-6">
                  {settingsError && (
                    <ErrorMessage
                      message={settingsError}
                      onDismiss={() => setSettingsError("")}
                    />
                  )}

                  <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                    <h3 className="text-base font-semibold text-slate-900">General</h3>
                    {!isAdmin && (
                      <p className="mt-1 text-xs text-slate-400">Name and manager can only be changed by an admin.</p>
                    )}
                    <div className="mt-4 space-y-4">
                      <Input
                        id="team-name"
                        label="Team name"
                        value={editForm.name ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({ ...currentForm, name: event.target.value }))
                        }
                        disabled={!isAdmin}
                      />

                      <div>
                        <label className="mb-1.5 block text-sm font-medium text-slate-700">Manager</label>
                        <UserPicker
                          users={users}
                          value={typeof editForm.manager === "number" ? editForm.manager : null}
                          onChange={(value) =>
                            setEditForm((currentForm) => ({
                              ...currentForm,
                              manager: value ?? undefined,
                            }))
                          }
                          disabled={!isAdmin || loadingUsers}
                        />
                      </div>
                    </div>
                  </section>

                  <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                    <h3 className="text-base font-semibold text-slate-900">AI Settings</h3>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <Input
                        id="team-ai-model"
                        label="Model"
                        value={editForm.ai_model ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            ai_model: event.target.value,
                          }))
                        }
                      />
                      <Input
                        id="team-monthly-budget"
                        label="Monthly token budget"
                        type="number"
                        value={String(editForm.monthly_token_budget ?? "")}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            monthly_token_budget: Number(event.target.value),
                          }))
                        }
                      />
                    </div>

                    <div className="mt-4">
                      <Input
                        id="team-ai-key"
                        label={`API key${selectedTeam.has_ai_api_key ? " (set)" : ""}`}
                        type="password"
                        value={editAiKey}
                        onChange={(event) => setEditAiKey(event.target.value)}
                        placeholder={selectedTeam.has_ai_api_key ? "Leave blank to keep current key" : "Enter key"}
                      />
                    </div>

                    <p className="mt-4 text-xs text-slate-500">
                      Tokens used this month:{" "}
                      <span className="font-semibold text-slate-700">
                        {selectedTeam.tokens_used_this_month.toLocaleString()}
                      </span>
                    </p>
                  </section>

                  <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                    <h3 className="text-base font-semibold text-slate-900">Integrations</h3>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <Input
                        id="team-jira-base-url"
                        label="Jira base URL"
                        value={editForm.jira_base_url ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            jira_base_url: event.target.value,
                          }))
                        }
                      />
                      <Input
                        id="team-jira-project-key"
                        label="Jira project key"
                        value={editForm.jira_project_key ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            jira_project_key: event.target.value,
                          }))
                        }
                      />
                      <Input
                        id="team-github-org"
                        label="GitHub org"
                        value={editForm.github_org ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            github_org: event.target.value,
                          }))
                        }
                      />
                      <Input
                        id="team-github-repo"
                        label="GitHub repo"
                        value={editForm.github_repo ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            github_repo: event.target.value,
                          }))
                        }
                      />
                      <Input
                        id="team-jenkins-url"
                        label="Jenkins URL"
                        value={editForm.jenkins_url ?? ""}
                        onChange={(event) =>
                          setEditForm((currentForm) => ({
                            ...currentForm,
                            jenkins_url: event.target.value,
                          }))
                        }
                      />
                    </div>
                  </section>
                </div>

                <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-5 py-4">
                    <h3 className="text-base font-semibold text-slate-900">Members</h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Manage the team membership list for this team.
                    </p>
                  </div>

                  <div className="space-y-4 px-5 py-4">
                    {memberError && (
                      <ErrorMessage message={memberError} onDismiss={() => setMemberError("")} />
                    )}

                    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm font-medium text-slate-800">Add member</p>
                      {!isAdmin && (
                        <p className="text-xs text-slate-400">Only admins can add new members. Contact your organization admin.</p>
                      )}
                      {isAdmin && (
                      <UserPicker
                        users={availableUsers}
                        value={addMemberUserId}
                        onChange={setAddMemberUserId}
                        placeholder="Select user"
                        disabled={loadingUsers}
                      />
                      )}
                      {isAdmin && (
                        <>
                          <select
                            value={addMemberRole}
                            onChange={(event) => setAddMemberRole(event.target.value as TeamMembershipRole)}
                            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
                          >
                            {TEAM_ROLE_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          <Button
                            size="sm"
                            isLoading={addingMember}
                            loadingText="Adding..."
                            onClick={handleAddMember}
                            disabled={addMemberUserId === null || loadingUsers}
                          >
                            Add member
                          </Button>
                        </>
                      )}
                    </div>

                    {loadingMembers ? (
                      <div className="flex justify-center py-10">
                        <Spinner />
                      </div>
                    ) : (membersPage?.results.length ?? 0) === 0 ? (
                      <p className="py-6 text-center text-sm text-slate-400">No members found.</p>
                    ) : (
                      <>
                        <div className="space-y-3">
                          {membersPage?.results.map((member) => (
                            <div
                              key={member.id}
                              className="rounded-lg border border-slate-200 px-4 py-3"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="font-medium text-slate-900">{member.full_name}</p>
                                  <p className="text-xs text-slate-400">{member.email}</p>
                                </div>
                                <button
                                  onClick={() => void handleRemoveMember(member)}
                                  className="text-xs text-red-500 hover:text-red-700"
                                >
                                  Remove
                                </button>
                              </div>
                              <div className="mt-3 flex items-center gap-3">
                                <select
                                  value={member.role}
                                  onChange={(event) =>
                                    void handleUpdateMemberRole(
                                      member,
                                      event.target.value as TeamMembershipRole
                                    )
                                  }
                                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
                                >
                                  {TEAM_ROLE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                                <span className="text-xs text-slate-500">
                                  Org role: {member.user_role.replaceAll("_", " ")}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>

                        <PaginationControls
                          page={membersPageNumber}
                          totalCount={membersPage?.count ?? 0}
                          hasNext={Boolean(membersPage?.next)}
                          hasPrevious={Boolean(membersPage?.previous)}
                          itemLabel="members"
                          onNext={() => setMembersPageNumber((currentPage) => currentPage + 1)}
                          onPrevious={() =>
                            setMembersPageNumber((currentPage) => Math.max(1, currentPage - 1))
                          }
                          className="px-0"
                        />
                      </>
                    )}
                  </div>
                </section>
              </div>
            </div>
          </main>
        ) : (
          <div className="flex flex-1 items-center justify-center bg-white text-sm text-slate-400">
            Select a team to manage it.
          </div>
        )}
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New team">
        <div className="space-y-4">
          {createError && <ErrorMessage message={createError} />}
          <Input
            id="new-team-name"
            label="Team name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((currentForm) => ({ ...currentForm, name: event.target.value }))
            }
            required
          />
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Manager</label>
            <UserPicker
              users={users}
              value={createForm.manager}
              onChange={(value) =>
                setCreateForm((currentForm) => ({ ...currentForm, manager: value }))
              }
              placeholder="Select manager"
              disabled={loadingUsers}
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setCreateOpen(false)}>
            Cancel
          </Button>
          <Button isLoading={creating} loadingText="Creating..." onClick={handleCreate}>
            Create team
          </Button>
        </div>
      </Modal>

      <Modal open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} title="Delete team">
        <p className="text-sm text-slate-600">
          Are you sure you want to delete <span className="font-semibold">{deleteTarget?.name}</span>?
          This cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button variant="danger" isLoading={deleting} loadingText="Deleting..." onClick={handleDeleteTeam}>
            Delete
          </Button>
        </div>
      </Modal>
    </AppLayout>
  );
}
