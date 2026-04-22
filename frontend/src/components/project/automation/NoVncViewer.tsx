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
    <div className="relative min-h-0 min-w-0 flex-1 overflow-hidden">
      <div ref={containerRef} className="absolute inset-0" />
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950">
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
  const [browserViewUrls, setBrowserViewUrls] = useState<string[]>([]);
  const [browserViewIndex, setBrowserViewIndex] = useState(0);

  useEffect(() => {
    if (!executionId || !enabled || !containerRef.current) return undefined;

    let cancelled = false;
    let fallbackTimer: number | undefined;
    let directConnected = false;
    setIsLoading(true);
    setError(null);
    setIsConnected(false);
    setBrowserViewUrls([]);
    setBrowserViewIndex(0);

    getStreamTicket(executionId)
      .then((ticket) => {
        if (cancelled || !containerRef.current) return;
        let viewUrls: string[];
        if (ticket.browser_view_urls?.length) {
          viewUrls = ticket.browser_view_urls;
        } else if (ticket.browser_view_url) {
          viewUrls = [ticket.browser_view_url];
        } else {
          viewUrls = [];
        }

        const RfbConstructor = getRfbConstructor();
        const rfb = new RfbConstructor(
          containerRef.current,
          buildWebSocketUrl(ticket.browser_websocket_path),
          { credentials: { password: "secret" } }
        );
        rfb.viewOnly = true;
        rfb.scaleViewport = true;
        rfb.resizeSession = true;
        rfb.addEventListener("connect", () => {
          directConnected = true;
          setIsConnected(true);
          setIsLoading(false);
        });
        rfb.addEventListener("disconnect", (event) => {
          setIsConnected(false);
          const detail = (event as CustomEvent<{ clean?: boolean; reason?: string }>).detail;
          if (!detail?.clean && viewUrls.length > 0 && !cancelled) {
            setBrowserViewUrls(viewUrls);
            setBrowserViewIndex(0);
            setError(null);
            setIsConnected(true);
            return;
          }
          if (!detail?.clean) {
            setError(detail?.reason || "Browser stream disconnected.");
          }
        });
        rfbRef.current = rfb;
        fallbackTimer = globalThis.setTimeout(() => {
          if (!cancelled && !directConnected && viewUrls.length > 0) {
            rfbRef.current?.disconnect();
            rfbRef.current = null;
            setBrowserViewUrls(viewUrls);
            setBrowserViewIndex(0);
            setError(null);
            setIsConnected(true);
          }
        }, 4000);
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : "Browser stream is unavailable.";
        setError(message);
      })
      .finally(() => setIsLoading(false));

    return () => {
      cancelled = true;
      if (fallbackTimer) globalThis.clearTimeout(fallbackTimer);
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
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-slate-950">
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

      {enabled && browserViewUrls.length > 0 && (
        <div className="flex min-h-0 flex-1 flex-col">
          {browserViewUrls.length > 1 && (
            <div className="flex shrink-0 items-center gap-2 border-b border-slate-800 px-3 py-2">
              <span className="text-xs text-slate-500">Node</span>
              {browserViewUrls.map((url, index) => (
                <button
                  key={url}
                  type="button"
                  onClick={() => setBrowserViewIndex(index)}
                  className={`rounded px-2 py-1 text-xs ${
                    browserViewIndex === index
                      ? "bg-slate-200 text-slate-950"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  {index + 1}
                </button>
              ))}
            </div>
          )}
          <iframe
            title="Browser session"
            src={browserViewUrls[browserViewIndex]}
            className="min-h-0 flex-1 border-0 bg-slate-950"
          />
        </div>
      )}
      {enabled && browserViewUrls.length === 0 && error && (
        <div className="flex flex-1 items-center justify-center px-6">
          <EmptyState title="Could not open browser" description={error} />
        </div>
      )}
      {enabled && browserViewUrls.length === 0 && !error && (
        <BrowserCanvas containerRef={containerRef} isLoading={isLoading} />
      )}
      {!enabled && <NoSessionView />}
    </div>
  );
}
