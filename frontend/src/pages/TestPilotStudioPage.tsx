import { useRef, useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createSpecificationSource } from "../api/specs";
import { getProject, getProjectTree } from "../api/projects/projects";
import AppLayout from "../components/layout/AppLayout";
import AIGenerationPanel from "../components/project/ai/AIGenerationPanel";
import { Button, Spinner } from "../components/ui";
import type { Project } from "../types/project";
import type { ProjectTree } from "../types/testing";

type AttachmentMenu = "closed" | "open";

interface LaunchState {
  objective: string;
  sourceRefs?: Record<string, unknown>;
  jiraIssueKey?: string;
}

export default function TestPilotStudioPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [project, setProject] = useState<Project | null>(null);
  const [tree, setTree] = useState<ProjectTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [objective, setObjective] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jiraIssueKey, setJiraIssueKey] = useState("");
  const [attachmentMenu, setAttachmentMenu] = useState<AttachmentMenu>("closed");
  const [launchState, setLaunchState] = useState<LaunchState | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);

    Promise.all([getProject(id), getProjectTree(id)])
      .then(([nextProject, nextTree]) => {
        if (cancelled) return;
        setProject(nextProject);
        setTree(nextTree);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the project workspace.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleGenerateScenarios() {
    if (!id) return;
    if (!objective.trim()) {
      setError("Describe the feature or workflow first.");
      return;
    }

    setPreparing(true);
    setError("");

    try {
      const sourceRefs: Record<string, unknown> = {};

      if (selectedFile) {
        const source = await createSpecificationSource({
          project: id,
          name: selectedFile.name,
          file: selectedFile,
          auto_parse: true,
          auto_import: true,
        });
        sourceRefs.specification_source_id = source.id;
      }

      setLaunchState({
        objective: objective.trim(),
        sourceRefs: Object.keys(sourceRefs).length ? sourceRefs : undefined,
        jiraIssueKey: jiraIssueKey.trim() || undefined,
      });
    } catch {
      setError("Could not prepare the attached requirement context.");
    } finally {
      setPreparing(false);
    }
  }

  async function refreshTree() {
    if (!id) return;
    const nextTree = await getProjectTree(id);
    setTree(nextTree);
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center">
          <Spinner size="lg" />
        </div>
      </AppLayout>
    );
  }

  if (!project || !tree) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
          Project not found.
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectName={project.name}>
      <div className="flex h-full overflow-hidden bg-[#f8fafc]">
        <aside className="hidden w-[72px] shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col lg:items-center lg:py-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-sm font-black text-white">
            TP
          </div>
          <div className="mt-8 flex flex-1 flex-col items-center gap-3">
            <StudioRailButton active label="TestPilot" />
            <StudioRailButton label="Runs" />
            <StudioRailButton label="Specs" />
            <StudioRailButton label="Data" />
          </div>
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full max-w-7xl flex-col px-5 py-6">
            <header className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">
                  TestPilot Studio
                </p>
                <h1 className="mt-1 text-lg font-semibold text-slate-950">{project.name}</h1>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => navigate(`/projects/${id}`)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-950"
                >
                  Repository
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/projects/${id}?tab=automation`)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-950"
                >
                  Automation
                </button>
              </div>
            </header>

            <section className="flex flex-1 flex-col items-center justify-center py-14">
              <div className="mb-7 flex h-16 w-16 items-center justify-center rounded-3xl border border-slate-200 bg-white shadow-sm">
                <svg className="h-9 w-9 text-slate-400" viewBox="0 0 48 48" fill="none">
                  <path
                    d="M15 23c0-5 4-9 9-9s9 4 9 9v4c0 5-4 9-9 9s-9-4-9-9v-4z"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                  <path
                    d="M10 25h28M17 27h5M26 27h5M18 35l-3 5M30 35l3 5"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                  />
                </svg>
              </div>

              <h2 className="text-center text-4xl font-semibold tracking-tight text-slate-950">
                What is your objective today?
              </h2>

              <div className="mt-12 w-full max-w-5xl rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_28px_90px_rgba(15,23,42,0.12)]">
                <textarea
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  rows={6}
                  placeholder="Describe the feature, workflow, or requirement you want to test."
                  className="min-h-[150px] w-full resize-none rounded-2xl border-0 bg-transparent px-1 text-lg text-slate-900 outline-none placeholder:text-slate-400"
                />

                {(selectedFile || jiraIssueKey) && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedFile && (
                      <AttachmentChip label={selectedFile.name} onRemove={() => setSelectedFile(null)} />
                    )}
                    {jiraIssueKey && (
                      <AttachmentChip label={`Jira ${jiraIssueKey}`} onRemove={() => setJiraIssueKey("")} />
                    )}
                  </div>
                )}

                {error && (
                  <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {error}
                  </div>
                )}

                <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
                    <button
                      type="button"
                      className="rounded-xl bg-sky-100 px-4 py-2 text-sm font-semibold text-sky-700"
                    >
                      Generate scenarios
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate(`/projects/${id}`)}
                      className="rounded-xl px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
                    >
                      Author browser test
                    </button>
                  </div>

                  <div className="relative flex items-center gap-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.xlsx,.csv,.txt"
                      className="hidden"
                      onChange={(event) => {
                        setSelectedFile(event.target.files?.[0] ?? null);
                        setAttachmentMenu("closed");
                      }}
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setAttachmentMenu((current) => (current === "open" ? "closed" : "open"))
                      }
                      className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                      title="Attach requirement context"
                    >
                      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12.79V8a5 5 0 00-10 0v8a3 3 0 006 0V8" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12v4a7 7 0 0014 0v-3" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                      title="Generation settings"
                    >
                      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7h10M18 7h2M4 17h2M10 17h10M7 4v6M17 14v6" />
                      </svg>
                    </button>
                    <Button
                      isLoading={preparing}
                      loadingText="Preparing"
                      onClick={() => void handleGenerateScenarios()}
                      className="rounded-2xl px-5"
                    >
                      Launch
                    </Button>

                    {attachmentMenu === "open" && (
                      <div className="absolute right-0 top-12 z-20 w-80 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-slate-700 hover:bg-slate-50"
                        >
                          <span>Upload from device</span>
                          <span className="text-xs text-slate-400">PDF/DOCX/XLSX/CSV</span>
                        </button>
                        <div className="border-t border-slate-100 p-4">
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Jira issue
                          </label>
                          <input
                            value={jiraIssueKey}
                            onChange={(event) => setJiraIssueKey(event.target.value)}
                            placeholder="BIAT-123"
                            className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-8 grid w-full max-w-5xl gap-3 md:grid-cols-3">
                <StudioCapability title="Grounded generation" text="Uses selected specs, imported records, FTS, and vector retrieval." />
                <StudioCapability title="Review before commit" text="Generated suites and cases stay draft until selected and saved." />
                <StudioCapability title="Browser authoring" text="Use repository cases for live Selenium authoring and noVNC control." />
              </div>
            </section>
          </div>
        </main>
      </div>

      <AIGenerationPanel
        open={Boolean(launchState)}
        projectId={id ?? ""}
        projectName={project.name}
        tree={tree}
        initialObjective={launchState?.objective ?? ""}
        initialSourceRefs={launchState?.sourceRefs}
        initialJiraIssueKey={launchState?.jiraIssueKey ?? ""}
        onClose={() => setLaunchState(null)}
        onCommitted={() => refreshTree()}
      />
    </AppLayout>
  );
}

function StudioRailButton({ active = false, label }: { active?: boolean; label: string }) {
  return (
    <button
      type="button"
      title={label}
      className={[
        "flex h-11 w-11 items-center justify-center rounded-2xl text-xs font-bold transition",
        active ? "bg-slate-100 text-slate-950" : "text-slate-400 hover:bg-slate-50 hover:text-slate-700",
      ].join(" ")}
    >
      {label.slice(0, 2)}
    </button>
  );
}

function AttachmentChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
      {label}
      <button type="button" onClick={onRemove} className="text-slate-400 hover:text-slate-700">
        x
      </button>
    </span>
  );
}

function StudioCapability({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  );
}
