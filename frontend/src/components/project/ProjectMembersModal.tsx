import { useEffect, useMemo, useState } from "react";
import {
  getProjectMembers,
  addProjectMember,
  updateProjectMember,
  removeProjectMember,
} from "../../api/projects/projects";
import { getTeamMembers } from "../../api/accounts/teams";
import { useAuthStore } from "../../store/authStore";
import { Modal, Button, Badge, Spinner } from "../ui";
import type { Project, ProjectMember, ProjectMemberRole } from "../../types/project";
import type { TeamMember } from "../../types/accounts";

const ROLE_OPTIONS: { value: ProjectMemberRole; label: string; description: string }[] = [
  { value: "owner", label: "Owner", description: "Full control of the project." },
  { value: "editor", label: "Editor", description: "Edit project content and work on tests." },
  { value: "viewer", label: "Viewer", description: "Read-only access." },
];
function roleColor(role: ProjectMemberRole) {
  switch (role) {
    case "owner":
      return "purple";
    case "editor":
      return "blue";
    case "viewer":
      return "slate";
    default:
      return "slate";
  }
}

function canManageProjectMembers(
  user: ReturnType<typeof useAuthStore.getState>["user"],
  project: Project,
) {
  if (!user) return false;
  const role = user.profile?.organization_role;
  if (user.is_staff || role === "platform_owner" || role === "org_admin") return true;
  return (
    user.profile?.team_memberships?.some(
      (m) => m.team === project.team && m.role === "manager",
    ) ?? false
  );
}

export default function ProjectMembersModal({
  open,
  project,
  onClose,
  onChanged,
}: {
  open: boolean;
  project: Project;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const currentUser = useAuthStore((s) => s.user);
  const canManage = canManageProjectMembers(currentUser, project);

  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showAdd, setShowAdd] = useState(false);
  const [addUserId, setAddUserId] = useState<string>("");
  const [addRole, setAddRole] = useState<ProjectMemberRole>("viewer");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    Promise.all([getProjectMembers(project.id), getTeamMembers(project.team)])
      .then(([m, tm]) => {
        setMembers(m);
        setTeamMembers(tm);
      })
      .catch(() => setError("Failed to load project members."))
      .finally(() => setLoading(false));
  }, [open, project.id, project.team]);

  const assignableTeamMembers = useMemo(() => {
    const assignedUserIds = new Set(members.map((m) => m.user_id));
    return teamMembers.filter(
      (tm) => tm.is_active && tm.user_role === "member" && !assignedUserIds.has(tm.user_id),
    );
  }, [teamMembers, members]);

  function resetAddForm() {
    setShowAdd(false);
    setAddUserId("");
    setAddRole("viewer");
    setAddError(null);
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!addUserId) return;
    setAdding(true);
    setAddError(null);
    try {
      const created = await addProjectMember(project.id, {
        user: Number(addUserId),
        role: addRole,
      });
      setMembers((prev) => [...prev, created]);
      resetAddForm();
      onChanged?.();
    } catch (err: unknown) {
      const data = (err as { response?: { data?: unknown } })?.response?.data;
      let msg = "Failed to add member.";
      if (typeof data === "string") {
        msg = data;
      } else if (data && typeof data === "object") {
        const dict = data as Record<string, unknown>;
        const first =
          (typeof dict.detail === "string" && dict.detail) ||
          (typeof dict.non_field_errors === "object" &&
            Array.isArray(dict.non_field_errors) &&
            dict.non_field_errors[0]) ||
          Object.entries(dict)
            .map(([k, v]) => {
              const value = Array.isArray(v) ? v[0] : v;
              return typeof value === "string" ? `${k}: ${value}` : null;
            })
            .filter(Boolean)
            .join(" · ");
        if (typeof first === "string" && first) msg = first;
      }
      setAddError(msg);
    } finally {
      setAdding(false);
    }
  }

  async function handleRoleChange(member: ProjectMember, role: ProjectMemberRole) {
    if (role === member.role) return;
    setBusyId(member.id);
    try {
      const updated = await updateProjectMember(project.id, member.id, role);
      setMembers((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      onChanged?.();
    } catch {
      window.alert("Failed to update role.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRemove(member: ProjectMember) {
    if (!window.confirm(`Remove ${member.full_name} from this project?`)) return;
    setBusyId(member.id);
    try {
      await removeProjectMember(project.id, member.id);
      setMembers((prev) => prev.filter((m) => m.id !== member.id));
      onChanged?.();
    } catch {
      window.alert("Failed to remove member.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Members — ${project.name}`}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="space-y-4 min-h-[240px]">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">
            {members.length} member{members.length !== 1 ? "s" : ""} ·{" "}
            <span className="text-slate-400">
              drawn from team{" "}
              <span className="text-slate-600 font-medium">{project.team_name}</span>
            </span>
          </p>
          {canManage && !showAdd && (
            <Button
              variant="secondary"
              onClick={() => setShowAdd(true)}
              disabled={assignableTeamMembers.length === 0 && !loading}
            >
              + Add member
            </Button>
          )}
        </div>

        {/* Add form */}
        {showAdd && canManage && (
          <form
            onSubmit={handleAdd}
            className="border border-slate-200 rounded-lg p-4 bg-slate-50 space-y-3"
          >
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Teammate <span className="text-red-500">*</span>
              </label>
              <select
                required
                value={addUserId}
                onChange={(e) => setAddUserId(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="">
                  {assignableTeamMembers.length === 0
                    ? "No eligible teammates"
                    : "Select a teammate…"}
                </option>
                {assignableTeamMembers.map((tm) => (
                  <option key={tm.user_id} value={tm.user_id}>
                    {tm.full_name || tm.email} · {tm.role}
                  </option>
                ))}
              </select>
              {assignableTeamMembers.length === 0 && !loading && (
                <p className="text-[11px] text-slate-500 mt-1">
                  Everyone eligible from <b>{project.team_name}</b> is already on this project.
                </p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Project role
              </label>
              <select
                value={addRole}
                onChange={(e) => setAddRole(e.target.value as ProjectMemberRole)}
                className="w-full px-3 py-2 rounded-md border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label} — {r.description}
                  </option>
                ))}
              </select>
            </div>
            {addError && <p className="text-xs text-red-600">{addError}</p>}
            <div className="flex items-center justify-end gap-2">
              <Button variant="secondary" onClick={resetAddForm} type="button">
                Cancel
              </Button>
              <Button
                type="submit"
                isLoading={adding}
                disabled={!addUserId || assignableTeamMembers.length === 0}
              >
                Add
              </Button>
            </div>
          </form>
        )}

        {/* List */}
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Spinner />
          </div>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : members.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-8">
            No members yet. Add teammates from <b>{project.team_name}</b> to collaborate.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
            {members.map((member) => {
              const isSelf = currentUser?.id === member.user_id;
              const busy = busyId === member.id;
              return (
                <li
                  key={member.id}
                  className="flex items-center gap-3 px-4 py-3 bg-white hover:bg-slate-50"
                >
                  <div className="w-9 h-9 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-sm font-semibold shrink-0">
                    {(member.first_name?.[0] || member.email?.[0] || "?").toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {member.full_name}
                      </p>
                      {isSelf && (
                        <span className="text-[10px] uppercase tracking-wide text-slate-400">
                          you
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 truncate">{member.email}</p>
                  </div>
                  {canManage && !isSelf ? (
                    <select
                      value={member.role}
                      disabled={busy}
                      onChange={(e) =>
                        handleRoleChange(member, e.target.value as ProjectMemberRole)
                      }
                      className="text-xs px-2 py-1 rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:opacity-50"
                    >
                      {ROLE_OPTIONS.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Badge label={member.role} color={roleColor(member.role)} />
                  )}
                  {canManage && !isSelf && (
                    <button
                      onClick={() => handleRemove(member)}
                      disabled={busy}
                      className="text-xs text-slate-400 hover:text-red-600 px-2 py-1 disabled:opacity-50"
                      aria-label="Remove member"
                    >
                      Remove
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Modal>
  );
}
