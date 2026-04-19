import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getProjects,
  createProject,
  updateProject,
  archiveProject,
  deleteProject,
  restoreProject,
} from "../api/projects/projects";
import { getTeams } from "../api/accounts/teams";
import { useAuthStore } from "../store/authStore";
import AppLayout from "../components/layout/AppLayout";
import { Button, EmptyState, Modal, Badge } from "../components/ui";
import type { Project, ProjectStatus } from "../types/project";
import type { Team } from "../types/accounts";

function canCreateProject(user: ReturnType<typeof useAuthStore.getState>["user"]) {
  if (!user) return false;
  const role = user.profile?.organization_role;
  if (user.is_staff || role === "platform_owner" || role === "org_admin") return true;
  return user.profile?.team_memberships?.some((m) => m.role === "manager") ?? false;
}

function canManageProject(user: ReturnType<typeof useAuthStore.getState>["user"], project: Project) {
  if (!user) return false;
  const role = user.profile?.organization_role;
  if (user.is_staff || role === "platform_owner" || role === "org_admin") return true;
  return (
    user.profile?.team_memberships?.some(
      (m) => m.team === project.team && m.role === "manager",
    ) ?? false
  );
}

function statusColor(status: ProjectStatus) {
  return status === "active" ? "green" : "slate";
}

function ProjectCard({
  project,
  canManage,
  onOpen,
  onEdit,
  onArchive,
  onDelete,
  onRestore,
}: {
  project: Project;
  canManage: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onRestore: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isArchived = project.status === "archived";

  useEffect(() => {
    if (!menuOpen) return;
    function onDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [menuOpen]);

  return (
    <div
      className={`relative bg-white rounded-xl border border-slate-200 p-5 hover:border-blue-300 hover:shadow-md transition-all group ${
        isArchived ? "opacity-70" : ""
      }`}
    >
      <button onClick={onOpen} className="text-left w-full">
        <div className="flex items-start justify-between mb-3">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm transition ${
              isArchived
                ? "bg-slate-100 text-slate-400"
                : "bg-blue-50 text-blue-600 group-hover:bg-blue-100"
            }`}
          >
            {project.name[0].toUpperCase()}
          </div>
          <Badge label={project.status} color={statusColor(project.status)} dot />
        </div>
        <h3 className="font-semibold text-slate-900 text-sm mb-0.5 truncate pr-6">
          {project.name}
        </h3>
        <p className="text-xs text-slate-500 mb-3 line-clamp-2 min-h-[2rem]">
          {project.description || "No description"}
        </p>
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>{project.team_name}</span>
          <span>
            {project.member_count} member{project.member_count !== 1 ? "s" : ""}
          </span>
        </div>
      </button>

      {canManage && (
        <div ref={menuRef} className="absolute top-3 right-3">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen((v) => !v);
            }}
            className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition"
            aria-label="Project actions"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 6a2 2 0 100-4 2 2 0 000 4zm0 6a2 2 0 100-4 2 2 0 000 4zm0 6a2 2 0 100-4 2 2 0 000 4z" />
            </svg>
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-8 w-40 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-10 text-sm">
              <button
                onClick={() => {
                  setMenuOpen(false);
                  onEdit();
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700"
              >
                Edit
              </button>
              {isArchived ? (
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onRestore();
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700"
                >
                  Restore
                </button>
              ) : (
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onArchive();
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-red-600"
                >
                  Archive
                </button>
              )}
              <button
                onClick={() => {
                  setMenuOpen(false);
                  onDelete();
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-red-600"
              >
                Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProjectsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [projects, setProjects] = useState<Project[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<ProjectStatus>("active");

  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "", team: "" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [editTarget, setEditTarget] = useState<Project | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "" });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getProjects(statusFilter), getTeams()])
      .then(([p, t]) => {
        setProjects(p);
        setTeams(t);
      })
      .finally(() => setLoading(false));
  }, [statusFilter]);

  const counts = useMemo(() => ({ active: 0, archived: 0 }), []);
  counts.active = projects.filter((p) => p.status === "active").length;
  counts.archived = projects.filter((p) => p.status === "archived").length;

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!createForm.name.trim() || !createForm.team.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const project = await createProject({
        name: createForm.name.trim(),
        description: createForm.description.trim(),
        team: createForm.team.trim(),
      });
      if (statusFilter === "active") setProjects((prev) => [project, ...prev]);
      setShowCreate(false);
      setCreateForm({ name: "", description: "", team: "" });
    } catch {
      setCreateError("Failed to create project.");
    } finally {
      setCreating(false);
    }
  }

  function openEdit(project: Project) {
    setEditTarget(project);
    setEditForm({ name: project.name, description: project.description });
    setEditError(null);
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editTarget || !editForm.name.trim()) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const updated = await updateProject(editTarget.id, {
        name: editForm.name.trim(),
        description: editForm.description.trim(),
      });
      setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setEditTarget(null);
    } catch {
      setEditError("Failed to update project.");
    } finally {
      setEditSaving(false);
    }
  }

  async function handleArchive(project: Project) {
    if (!window.confirm(`Archive "${project.name}"? It will be hidden from active views.`)) return;
    try {
      await archiveProject(project.id);
      setProjects((prev) => prev.filter((p) => p.id !== project.id));
    } catch {
      window.alert("Failed to archive project.");
    }
  }

  async function handleRestore(project: Project) {
    try {
      await restoreProject(project.id);
      setProjects((prev) => prev.filter((p) => p.id !== project.id));
    } catch {
      window.alert("Failed to restore project.");
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteProject(deleteTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch {
      setDeleteError("Failed to delete project.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Projects</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {projects.length} {statusFilter} project{projects.length !== 1 ? "s" : ""}
            </p>
          </div>
          {canCreateProject(user) && (
            <Button onClick={() => setShowCreate(true)}>+ New Project</Button>
          )}
        </div>

        {/* Status tabs */}
        <div className="flex items-center gap-1 border-b border-slate-200 mb-6">
          {(["active", "archived"] as ProjectStatus[]).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
                statusFilter === s
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {s === "active" ? "Active" : "Archived"}
            </button>
          ))}
        </div>

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
                <div className="w-9 h-9 rounded-lg bg-slate-100 mb-3" />
                <div className="h-4 bg-slate-100 rounded mb-2 w-3/4" />
                <div className="h-3 bg-slate-100 rounded w-full mb-1" />
                <div className="h-3 bg-slate-100 rounded w-2/3" />
              </div>
            ))}
          </div>
        ) : projects.length === 0 ? (
          <EmptyState
            title={statusFilter === "active" ? "No active projects" : "No archived projects"}
            description={
              statusFilter === "active"
                ? "Create your first project to start organizing test suites and cases."
                : "Projects you archive will appear here."
            }
            action={
              statusFilter === "active" && canCreateProject(user) ? (
                <Button onClick={() => setShowCreate(true)}>Create Project</Button>
              ) : undefined
            }
            icon={
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M3 7a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
                />
              </svg>
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {projects.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                canManage={canManageProject(user, p)}
                onOpen={() => navigate(`/projects/${p.id}`)}
                onEdit={() => openEdit(p)}
                onArchive={() => handleArchive(p)}
                onDelete={() => {
                  setDeleteTarget(p);
                  setDeleteError(null);
                }}
                onRestore={() => handleRestore(p)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create modal */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="New Project"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button form="create-project-form" type="submit" isLoading={creating}>
              Create
            </Button>
          </>
        }
      >
        <form id="create-project-form" onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Project name <span className="text-red-500">*</span>
            </label>
            <input
              required
              value={createForm.name}
              onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Banking App — Regression"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Team <span className="text-red-500">*</span>
            </label>
            <select
              required
              value={createForm.team}
              onChange={(e) => setCreateForm((f) => ({ ...f, team: e.target.value }))}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent bg-white"
            >
              <option value="">Select a team…</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
            <textarea
              rows={3}
              value={createForm.description}
              onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Optional description"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent resize-none"
            />
          </div>
          {createError && <p className="text-sm text-red-600">{createError}</p>}
        </form>
      </Modal>

      {/* Edit modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title="Edit Project"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditTarget(null)}>
              Cancel
            </Button>
            <Button form="edit-project-form" type="submit" isLoading={editSaving}>
              Save
            </Button>
          </>
        }
      >
        <form id="edit-project-form" onSubmit={handleEdit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Project name <span className="text-red-500">*</span>
            </label>
            <input
              required
              value={editForm.name}
              onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
            <textarea
              rows={3}
              value={editForm.description}
              onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent resize-none"
            />
          </div>
          {editError && <p className="text-sm text-red-600">{editError}</p>}
        </form>
      </Modal>

      <Modal
        open={!!deleteTarget}
        onClose={() => {
          if (deleting) return;
          setDeleteTarget(null);
          setDeleteError(null);
        }}
        title="Delete Project"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setDeleteTarget(null);
                setDeleteError(null);
              }}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void handleDelete()} isLoading={deleting}>
              Delete
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Delete <span className="font-semibold text-slate-900">{deleteTarget?.name}</span> permanently?
          </p>
          <p className="text-sm text-slate-500">
            This removes the project from the workspace. Use archive when you only want to hide it from active work.
          </p>
          {deleteError && <p className="text-sm text-red-600">{deleteError}</p>}
        </div>
      </Modal>
    </AppLayout>
  );
}
