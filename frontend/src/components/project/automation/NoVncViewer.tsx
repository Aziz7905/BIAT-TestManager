import { useEffect, useRef, useState } from "react";
import RFB from "@novnc/novnc/lib/rfb.js";
import { getStreamTicket } from "../../../api/automation/executions";
import EmptyState from "../../ui/EmptyState";
import Spinner from "../../ui/Spinner";

type RfbInstance = EventTarget & {
  viewOnly: boolean;
  scaleViewport: boolean;
  resizeSession: boolean;
  disconnect: () => void;
};

type RfbConstructor = new (
  target: HTMLElement,
  url: string,
  options?: { credentials?: { password?: string } },
) => RfbInstance;

interface NoVncViewerProps {
  readonly executionId: string | null;
  readonly enabled: boolean;
}

function getRfbConstructor(): RfbConstructor {
  const moduleValue = RFB as unknown as RfbConstructor | { default?: RfbConstructor };
  if (
    typeof moduleValue === "object" &&
    moduleValue !== null &&
    "default" in moduleValue &&
    typeof moduleValue.default === "function"
  ) {
    return moduleValue.default;
  }
  return moduleValue as RfbConstructor;
}

function buildWebSocketUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || globalThis.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function getStatusDotClass(enabled: boolean, connected: boolean, loading: boolean): string {
  if (enabled && connected) return "bg-green-400";
  if (enabled && loading) return "animate-pulse bg-slate-500";
  if (enabled) return "bg-red-400";
  return "animate-pulse bg-slate-600";
}

function getStatusLabel(enabled: boolean, connected: boolean, loading: boolean): string {
  if (enabled && connected) return "Connected";
  if (enabled && loading) return "Connecting...";
  if (enabled) return "Disconnected";
  return "Waiting for browser session";
}

function NoSessionView() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-slate-500">
      <p className="text-sm">No browser session active</p>
      <p className="max-w-xs text-center text-xs text-slate-600">
        Browser streaming requires Selenium Grid and the script to call{" "}
        <code className="rounded bg-slate-800 px-1 text-slate-300">report_session_started()</code>
      </p>
    </div>
  );
}

function BrowserCanvas({
  containerRef,
  isLoading,
}: {
  readonly containerRef: { current: HTMLDivElement | null };
  readonly isLoading: boolean;
}) {
  return (
    <div className="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-slate-950">
      <div ref={containerRef} className="absolute inset-0" />
      {isLoading && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <Spinner size="md" />
        </div>
      )}
    </div>
  );
}

export default function NoVncViewer({ executionId, enabled }: NoVncViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rfbRef = useRef<RfbInstance | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInteractive, setIsInteractive] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!executionId || !enabled || !containerRef.current) return undefined;

    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    setIsLoading(true);
    setError(null);
    setIsConnected(false);

    getStreamTicket(executionId)
      .then((ticket) => {
        if (cancelled || !containerRef.current) return;

        const target = containerRef.current;
        const RfbConstructor = getRfbConstructor();
        const rfb = new RfbConstructor(
          target,
          buildWebSocketUrl(ticket.browser_websocket_path),
          { credentials: { password: "secret" } }
        );
        rfb.viewOnly = true;
        rfb.scaleViewport = true;
        rfb.resizeSession = true;

        const triggerRescale = () => {
          globalThis.dispatchEvent(new Event("resize"));
        };

        rfb.addEventListener("connect", () => {
          setIsConnected(true);
          setIsLoading(false);
          globalThis.setTimeout(triggerRescale, 50);
          globalThis.setTimeout(triggerRescale, 300);
          globalThis.setTimeout(triggerRescale, 1000);
        });
        rfb.addEventListener("disconnect", (event) => {
          setIsConnected(false);
          const detail = (event as CustomEvent<{ clean?: boolean; reason?: string }>).detail;
          if (!detail?.clean) {
            setError(detail?.reason || "Browser stream disconnected.");
          }
        });
        rfbRef.current = rfb;

        if (typeof ResizeObserver !== "undefined") {
          resizeObserver = new ResizeObserver(() => triggerRescale());
          resizeObserver.observe(target);
        }
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : "Browser stream is unavailable.";
        setError(message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      rfbRef.current?.disconnect();
      rfbRef.current = null;
      setIsConnected(false);
    };
  }, [enabled, executionId]);

  useEffect(() => {
    if (rfbRef.current) {
      rfbRef.current.viewOnly = !isInteractive;
    }
  }, [isInteractive]);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-950">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-800 px-3 py-1.5">
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${getStatusDotClass(enabled, isConnected, isLoading)}`}
          />
          <span className="text-xs text-slate-400">
            {getStatusLabel(enabled, isConnected, isLoading)}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIsInteractive((prev) => !prev)}
          disabled={!isConnected}
          className={
            isInteractive
              ? "rounded px-2.5 py-1 text-xs font-medium bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30 transition"
              : "rounded px-2.5 py-1 text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-40 transition"
          }
        >
          {isInteractive ? "Release control" : "Take control"}
        </button>
      </div>

      {!enabled && <NoSessionView />}
      {enabled && error && !isConnected && (
        <div className="flex flex-1 items-center justify-center px-6">
          <EmptyState title="Browser stream unavailable" description={error} />
        </div>
      )}
      {enabled && (!error || isConnected) && (
        <BrowserCanvas containerRef={containerRef} isLoading={isLoading} />
      )}
    </div>
  );
}
