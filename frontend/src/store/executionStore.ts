import { create } from "zustand";
import { getStreamTicket } from "../api/automation/executions";
import type {
  ExecutionArtifact,
  ExecutionCheckpoint,
  ExecutionStep,
  ExecutionStreamEvent,
  TestExecution,
  TestResult,
} from "../types/automation";

interface ExecutionStreamState {
  selectedExecutionId: string | null;
  execution: TestExecution | null;
  steps: ExecutionStep[];
  pendingCheckpoints: ExecutionCheckpoint[];
  artifacts: ExecutionArtifact[];
  result: TestResult | null;
  isConnecting: boolean;
  streamError: string | null;
  connect: (executionId: string) => Promise<void>;
  disconnect: () => void;
  mergeEvent: (event: ExecutionStreamEvent) => void;
  setExecution: (execution: TestExecution) => void;
}

let socket: WebSocket | null = null;

function buildWebSocketUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || globalThis.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function upsertStep(steps: ExecutionStep[], nextStep: ExecutionStep): ExecutionStep[] {
  const existingIndex = steps.findIndex((step) => step.id === nextStep.id);
  if (existingIndex === -1) {
    return [...steps, nextStep].sort((a, b) => a.step_index - b.step_index);
  }
  const next = [...steps];
  next[existingIndex] = nextStep;
  return next.sort((a, b) => a.step_index - b.step_index);
}

function upsertCheckpoint(
  checkpoints: ExecutionCheckpoint[],
  checkpoint: ExecutionCheckpoint
): ExecutionCheckpoint[] {
  if (checkpoint.status !== "pending") {
    return checkpoints.filter((item) => item.id !== checkpoint.id);
  }
  const existingIndex = checkpoints.findIndex((item) => item.id === checkpoint.id);
  if (existingIndex === -1) {
    return [...checkpoints, checkpoint];
  }
  const next = [...checkpoints];
  next[existingIndex] = checkpoint;
  return next;
}

function upsertArtifact(
  artifacts: ExecutionArtifact[],
  artifact: ExecutionArtifact
): ExecutionArtifact[] {
  if (!artifact.id) {
    return [artifact, ...artifacts];
  }
  if (artifacts.some((item) => item.id === artifact.id)) {
    return artifacts.map((item) => (item.id === artifact.id ? artifact : item));
  }
  return [artifact, ...artifacts];
}

export const useExecutionStore = create<ExecutionStreamState>((set, get) => ({
  selectedExecutionId: null,
  execution: null,
  steps: [],
  pendingCheckpoints: [],
  artifacts: [],
  result: null,
  isConnecting: false,
  streamError: null,

  connect: async (executionId) => {
    get().disconnect();
    set({
      selectedExecutionId: executionId,
      execution: null,
      steps: [],
      pendingCheckpoints: [],
      artifacts: [],
      result: null,
      isConnecting: true,
      streamError: null,
    });

    try {
      const ticket = await getStreamTicket(executionId);
      socket = new WebSocket(buildWebSocketUrl(ticket.websocket_path));
      socket.onopen = () => set({ isConnecting: false });
      socket.onerror = () => {
        set({
          isConnecting: false,
          streamError: "Live execution stream is unavailable.",
        });
      };
      socket.onclose = () => set({ isConnecting: false });
      socket.onmessage = (message) => {
        try {
          get().mergeEvent(JSON.parse(message.data) as ExecutionStreamEvent);
        } catch {
          set({ streamError: "Received an invalid execution event." });
        }
      };
    } catch {
      set({
        isConnecting: false,
        streamError: "Could not open the live execution stream.",
      });
    }
  },

  disconnect: () => {
    if (socket) {
      socket.close();
      socket = null;
    }
  },

  mergeEvent: (event) => {
    if (event.type === "execution.snapshot") {
      set({
        execution: event.payload.execution,
        steps: event.payload.steps,
        pendingCheckpoints: event.payload.pending_checkpoints,
        artifacts: event.payload.artifacts,
        result: event.payload.result,
      });
      return;
    }

    if (event.type === "execution.status_changed") {
      set({ execution: event.payload });
      return;
    }

    if (event.type === "execution.step_updated") {
      set((state) => ({ steps: upsertStep(state.steps, event.payload) }));
      return;
    }

    if (event.type === "execution.result_ready") {
      set({ result: event.payload });
      return;
    }

    if (event.type === "execution.artifact_created") {
      set((state) => ({ artifacts: upsertArtifact(state.artifacts, event.payload) }));
      return;
    }

    if (
      event.type === "execution.checkpoint_requested" ||
      event.type === "execution.checkpoint_resolved" ||
      event.type === "execution.checkpoint_expired"
    ) {
      set((state) => ({
        pendingCheckpoints: upsertCheckpoint(state.pendingCheckpoints, event.payload),
      }));
    }
  },

  setExecution: (execution) => set({ execution }),
}));
