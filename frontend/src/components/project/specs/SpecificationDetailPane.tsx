import { useMemo, useState } from "react";
import { Badge, Button, EmptyState, Spinner } from "../../ui";
import type { SpecificationDetail } from "../../../types/specs";
import { coverageColor, formatDateTime, indexStatusColor, sourceTypeLabel } from "./shared";

interface SpecificationDetailPaneProps {
  detail: SpecificationDetail | null;
  loading: boolean;
  error: string | null;
  deleting: boolean;
  onOpenCase: (caseId: string, scenarioId: string) => void;
  onDelete: () => void;
}

export default function SpecificationDetailPane({
  detail,
  loading,
  error,
  deleting,
  onOpenCase,
  onDelete,
}: SpecificationDetailPaneProps) {
  const [showChunks, setShowChunks] = useState(false);

  const chunks = useMemo(() => detail?.chunks ?? [], [detail]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return <EmptyState title="Could not load this specification" description={error} />;
  }

  if (!detail) {
    return (
      <EmptyState
        title="Select a specification"
        description="Choose an imported requirement to inspect coverage and traceability."
      />
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="border-b border-slate-200 px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-lg font-semibold text-slate-900">{detail.title}</h3>
              <Badge label={detail.coverage_status} color={coverageColor(detail.coverage_status)} />
              <Badge label={sourceTypeLabel(detail.source_type)} />
              <Badge label={detail.index_status} color={indexStatusColor(detail.index_status)} />
            </div>
            <p className="mt-1 text-xs text-slate-400">{detail.project_name}</p>
            <p className="mt-1 text-sm text-slate-500">
              {detail.external_reference || "No external reference"} • Updated {formatDateTime(detail.updated_at)}
            </p>
          </div>
          <Button variant="danger" size="sm" onClick={onDelete} isLoading={deleting}>
            Delete spec
          </Button>
        </div>
      </div>

      <div className="space-y-6 px-6 py-5">
        <div className="rounded-lg border border-slate-200 px-4 py-4">
          <div className="mb-3 flex items-center justify-between gap-4">
            <h4 className="text-sm font-semibold text-slate-900">Requirement</h4>
            <p className="text-xs text-slate-500">{detail.chunk_count} chunks indexed</p>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{detail.content}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <SummaryCard label="Linked cases" value={detail.linked_test_case_count} />
          <SummaryCard label="Linked scenarios" value={detail.linked_scenario_count} />
          <SummaryCard label="Linked suites" value={detail.linked_suite_count} />
        </div>

        <div className="rounded-lg border border-slate-200 px-4 py-4">
          <div className="mb-4">
            <h4 className="text-sm font-semibold text-slate-900">Linked test cases</h4>
            <p className="mt-0.5 text-xs text-slate-500">
              Link cases to this spec from the case editor in Repository. Open a case here to navigate there.
            </p>
          </div>

          {detail.linked_test_cases.length === 0 ? (
            <EmptyState
              title="No linked test cases"
              description="This requirement is not yet covered by any case."
            />
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Case</th>
                    <th className="px-4 py-3">Scenario</th>
                    <th className="px-4 py-3">Suite</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {detail.linked_test_cases.map((testCase) => (
                    <tr key={testCase.id}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{testCase.title}</p>
                        <p className="mt-0.5 text-xs text-slate-500">v{testCase.version}</p>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{testCase.scenario_title}</td>
                      <td className="px-4 py-3 text-slate-600">{testCase.suite_name}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Badge label={testCase.status} />
                          <Badge label={testCase.automation_status} />
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => onOpenCase(testCase.id, testCase.scenario_id)}
                        >
                          Open in repository
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 px-4 py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">Retrieval chunks</h4>
              <p className="mt-0.5 text-xs text-slate-500">
                Lower-priority retrieval detail for later AI or search workflows.
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={() => setShowChunks((value) => !value)}>
              {showChunks ? "Hide chunks" : "Show chunks"}
            </Button>
          </div>

          {showChunks && (
            <div className="mt-4 space-y-3">
              {chunks.length === 0 ? (
                <p className="text-sm text-slate-500">No chunks stored for this specification.</p>
              ) : (
                chunks.map((chunk) => (
                  <div key={chunk.id} className="rounded-lg border border-slate-200 px-4 py-3">
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Chunk {chunk.chunk_index + 1} • {chunk.chunk_type}
                      </p>
                      <p className="text-xs text-slate-400">{chunk.token_count} tokens</p>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{chunk.content}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
