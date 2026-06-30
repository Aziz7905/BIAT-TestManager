import type { RefObject } from "react";
import type { Project } from "../../../types/project";
import { Button } from "../../ui";
import type { AttachmentMenu, LaunchContext, ProjectTargetMode } from "../testPilot.types";
import { targetLabel } from "../testPilot.utils";
import {
  CloseIcon,
  DocumentStackIcon,
  JiraLogo,
  SpreadsheetIcon,
} from "../icons/TestPilotIcons";

interface TestPilotLaunchViewProps {
  attachmentMenu: AttachmentMenu;
  attachmentMenuRef: RefObject<HTMLDivElement | null>;
  availableProjects: Project[];
  canCreateProject: boolean;
  canLaunch: boolean;
  error: string;
  fileInputRef: RefObject<HTMLInputElement | null>;
  initialContext: LaunchContext;
  jiraIssueKey: string;
  launching: boolean;
  objective: string;
  project: Project | null;
  selectedFile: File | null;
  selectedProjectId: string;
  targetMode: ProjectTargetMode;
  targetPanelOpen: boolean;
  onAttachmentMenuChange: (state: AttachmentMenu) => void;
  onGenerate: () => void;
  onJiraIssueKeyChange: (value: string) => void;
  onObjectiveChange: (value: string) => void;
  onProjectChange: (projectId: string) => void;
  onSelectedFileChange: (file: File | null) => void;
  onTargetModeChange: (mode: ProjectTargetMode) => void;
  onTargetPanelOpenChange: (open: boolean | ((current: boolean) => boolean)) => void;
}

export default function TestPilotLaunchView({
  attachmentMenu,
  attachmentMenuRef,
  availableProjects,
  canCreateProject,
  canLaunch,
  error,
  fileInputRef,
  initialContext,
  jiraIssueKey,
  launching,
  objective,
  project,
  selectedFile,
  selectedProjectId,
  targetMode,
  targetPanelOpen,
  onAttachmentMenuChange,
  onGenerate,
  onJiraIssueKeyChange,
  onObjectiveChange,
  onProjectChange,
  onSelectedFileChange,
  onTargetModeChange,
  onTargetPanelOpenChange,
}: Readonly<TestPilotLaunchViewProps>) {
  return (
    <section
      className="relative flex h-full flex-col items-center justify-center overflow-y-auto bg-slate-50 px-4 py-4 sm:px-6"
      style={{
        backgroundImage:
          [
            "linear-gradient(180deg, rgba(255,255,255,0.46) 0%, rgba(255,255,255,0.30) 48%, rgba(255,255,255,0.16) 100%)",
            "linear-gradient(90deg, rgba(255,255,255,0.56) 0%, rgba(255,255,255,0.26) 50%, rgba(255,255,255,0.52) 100%)",
            "url('/testpilot-prompt-bg.png')",
          ].join(", "),
        backgroundPosition: "center",
        backgroundSize: "cover",
      }}
    >
      <div className="w-full max-w-[900px]">
        <style>
          {`
            @keyframes testpilot-logo-float {
              0%, 100% { transform: translateY(0); }
              50% { transform: translateY(-5px); }
            }
          `}
        </style>
        <div className="mb-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_14px_36px_rgba(15,23,42,0.12)] transition duration-300 hover:shadow-[0_18px_42px_rgba(15,23,42,0.16)] [animation:testpilot-logo-float_4s_ease-in-out_infinite]">
            <img src="/biat_logo.png" alt="BIAT logo" className="h-full w-full object-cover" />
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#17233C] sm:text-[34px]">
            What is your objective today?
          </h1>
          <p className="mt-1.5 text-sm font-medium text-[#64748B] sm:text-base">
            Describe a feature, workflow, or requirement to generate structured test coverage.
          </p>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/94 p-4 shadow-[0_18px_45px_rgba(11,23,51,0.18)] transition duration-300 hover:-translate-y-0.5 hover:shadow-[0_22px_54px_rgba(11,23,51,0.20)] sm:p-5">
          <div className="mb-3 flex items-center justify-between gap-4">
            <div className="min-w-0">
              <span className="block truncate text-sm font-semibold text-[#17233C]">
                Project: {project ? project.name : targetLabel(targetMode, availableProjects).replace("Project: ", "")}
              </span>
            </div>
            {!initialContext.projectId && (
              <button
                type="button"
                onClick={() => onTargetPanelOpenChange((current) => !current)}
                className="shrink-0 rounded-md px-2 py-1.5 text-sm font-semibold text-[#2563EB] transition hover:bg-[#EAF4FF] focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
              >
                Change project
              </button>
            )}
          </div>

          {(initialContext.labels.suite ||
            initialContext.labels.section ||
            initialContext.labels.scenario ||
            initialContext.labels.case) && (
            <div className="mb-4 flex flex-wrap gap-2">
              {initialContext.labels.suite && <ContextChip label={`Suite: ${initialContext.labels.suite}`} />}
              {initialContext.labels.section && <ContextChip label={`Section: ${initialContext.labels.section}`} />}
              {initialContext.labels.scenario && <ContextChip label={`Scenario: ${initialContext.labels.scenario}`} />}
              {initialContext.labels.case && <ContextChip label={`Case: ${initialContext.labels.case}`} />}
            </div>
          )}

          {targetPanelOpen && (
            <ProjectTargetPanel
              availableProjects={availableProjects}
              canCreateProject={canCreateProject}
              selectedProjectId={selectedProjectId}
              targetMode={targetMode}
              onTargetModeChange={onTargetModeChange}
              onProjectChange={onProjectChange}
            />
          )}

          {(selectedFile || jiraIssueKey) && (
            <div className="mb-3 flex flex-wrap gap-2">
              {selectedFile && (
                <AttachmentChip label={selectedFile.name} onRemove={() => onSelectedFileChange(null)} />
              )}
              {jiraIssueKey && (
                <AttachmentChip kind="jira" label={`Jira ${jiraIssueKey}`} onRemove={() => onJiraIssueKeyChange("")} />
              )}
            </div>
          )}

          <div>
            <label htmlFor="testpilot-objective" className="text-sm font-semibold text-[#17233C]">
              Objective or requirements
            </label>
            <textarea
              id="testpilot-objective"
              value={objective}
              onChange={(event) => onObjectiveChange(event.target.value)}
              rows={5}
              placeholder="Describe the workflow, rule, user story, or file context to test."
              className="mt-2 h-[clamp(104px,16vh,140px)] w-full resize-none rounded-xl border border-[#D9E8F7] bg-white px-4 py-3 text-base leading-6 text-[#17233C] outline-none placeholder:text-slate-400 transition focus:border-[#5AB8FF] focus:ring-2 focus:ring-[#EAF4FF]"
            />
            {error && <ErrorBanner message={error} />}
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div ref={attachmentMenuRef} className="relative flex flex-wrap items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.xlsx,.csv,.txt"
                  className="hidden"
                  onChange={(event) => {
                    onSelectedFileChange(event.target.files?.[0] ?? null);
                    onAttachmentMenuChange("closed");
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-[#17233C] transition duration-200 hover:-translate-y-0.5 hover:bg-[#EAF4FF] hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
                  aria-label="Upload requirement file"
                  title="Upload requirement file"
                >
                  <DocumentStackIcon />
                </button>
                <button
                  type="button"
                  onClick={() => onAttachmentMenuChange(attachmentMenu === "open" ? "closed" : "open")}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-[#17233C] transition duration-200 hover:-translate-y-0.5 hover:bg-[#EAF4FF] hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
                  aria-label="Import from Jira"
                  title="Import from Jira"
                >
                  <JiraLogo />
                </button>
                {attachmentMenu === "open" && (
                  <AttachmentMenuPanel
                    jiraIssueKey={jiraIssueKey}
                    onClose={() => onAttachmentMenuChange("closed")}
                    onJiraIssueKeyChange={onJiraIssueKeyChange}
                  />
                )}
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button
                  type="button"
                  disabled={!canLaunch || launching}
                  isLoading={launching}
                  loadingText="Generating"
                  onClick={onGenerate}
                  className="border-[#0B1733] bg-[#0B1733] text-white hover:bg-[#17233C] focus:ring-[#2563EB] disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                >
                  Generate test plan
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ProjectTargetPanel({
  availableProjects,
  canCreateProject,
  selectedProjectId,
  targetMode,
  onProjectChange,
  onTargetModeChange,
}: Readonly<{
  availableProjects: Project[];
  canCreateProject: boolean;
  selectedProjectId: string;
  targetMode: ProjectTargetMode;
  onProjectChange: (projectId: string) => void;
  onTargetModeChange: (mode: ProjectTargetMode) => void;
}>) {
  return (
    <div className="mb-4 rounded-xl border border-[#D9E8F7] bg-[#F8FBFF] p-3">
      <div className="grid gap-2 md:grid-cols-3">
        <TargetOption
          active={targetMode === "auto"}
          label="Auto"
          text="Use project context, one existing project, or create a new one when allowed."
          onClick={() => onTargetModeChange("auto")}
        />
        <TargetOption
          active={targetMode === "existing"}
          label="Existing"
          text="Generate into a project you choose."
          onClick={() => onTargetModeChange("existing")}
        />
        <TargetOption
          active={targetMode === "new"}
          disabled={!canCreateProject}
          label="New project"
          text={canCreateProject ? "Create a new project from this prompt." : "Only managers can create projects."}
          onClick={() => onTargetModeChange("new")}
        />
      </div>
      {targetMode === "existing" && (
        <div className="mt-3 rounded-lg border border-[#D9E8F7] bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <label htmlFor="testpilot-project-select" className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-[#17233C]">Choose a project</span>
              <span className="mt-1 block text-xs text-[#64748B]">
                Select the repository where TestPilot should create the generated tests.
              </span>
              <select
                id="testpilot-project-select"
                value={selectedProjectId}
                onChange={(event) => onProjectChange(event.target.value)}
                className="mt-3 h-11 w-full rounded-lg border border-[#D9E8F7] bg-white px-3 text-sm text-[#17233C] shadow-sm outline-none transition focus:border-[#5AB8FF] focus:ring-2 focus:ring-[#EAF4FF]"
              >
                <option value="">Select a project</option>
                {availableProjects.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <span className="shrink-0 rounded-full bg-[#EAF4FF] px-3 py-1 text-xs font-semibold text-[#2563EB]">
              {availableProjects.length} available
            </span>
          </div>
          {!availableProjects.length && (
            <p className="mt-3 text-sm text-[#64748B]">No active projects available.</p>
          )}
        </div>
      )}
    </div>
  );
}

function TargetOption({
  active,
  disabled = false,
  label,
  text,
  onClick,
}: Readonly<{
  active: boolean;
  disabled?: boolean;
  label: string;
  text: string;
  onClick: () => void;
}>) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={[
        "rounded-lg border px-3 py-2 text-left transition duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-50",
        active
          ? "border-[#5AB8FF] bg-white text-[#17233C] shadow-sm"
          : "border-[#D9E8F7] bg-white/80 text-[#64748B] hover:border-[#CFE7FF] hover:bg-white",
      ].join(" ")}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="mt-1 block text-xs leading-5">{text}</span>
    </button>
  );
}

function AttachmentMenuPanel({
  jiraIssueKey,
  onClose,
  onJiraIssueKeyChange,
}: Readonly<{
  jiraIssueKey: string;
  onClose: () => void;
  onJiraIssueKeyChange: (value: string) => void;
}>) {
  return (
    <div className="absolute bottom-11 left-0 z-20 w-72 overflow-hidden rounded-lg border border-blue-100 bg-white shadow-2xl">
      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="testpilot-jira" className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <JiraLogo />
            Jira issue
          </label>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#5AB8FF]"
            aria-label="Close Jira import"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>
        <input
          id="testpilot-jira"
          value={jiraIssueKey}
          onChange={(event) => onJiraIssueKeyChange(event.target.value)}
          placeholder="BIAT-123"
          className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
        />
      </div>
    </div>
  );
}

function ContextChip({ label }: Readonly<{ label: string }>) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
      {label}
    </span>
  );
}

function AttachmentChip({
  kind,
  label,
  onRemove,
}: Readonly<{ kind?: "jira"; label: string; onRemove: () => void }>) {
  const lowerLabel = label.toLowerCase();
  const icon = kind === "jira" ? <JiraLogo /> : lowerLabel.endsWith(".xlsx") || lowerLabel.endsWith(".csv") ? <SpreadsheetIcon /> : <DocumentStackIcon />;
  return (
    <span className="inline-flex max-w-full items-center gap-2 rounded-md border border-slate-200 bg-white/90 px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm">
      {icon}
      <span className="max-w-[260px] truncate">{label}</span>
      <button type="button" onClick={onRemove} aria-label={`Remove ${label}`} className="text-slate-400 hover:text-slate-700">
        <CloseIcon className="h-3.5 w-3.5" />
      </button>
    </span>
  );
}

function ErrorBanner({ message }: Readonly<{ message: string }>) {
  return (
    <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </div>
  );
}
