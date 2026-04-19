import { useCallback, useEffect, useState } from "react";
import {
  deleteSpecification,
  deleteSpecificationSource,
  deleteSelectedSpecificationSourceRecords,
  getSpecificationDetail,
  getSpecificationSourceDetail,
  getSpecificationSourcesPage,
  getSpecificationsPage,
  importSpecificationSource,
  parseSpecificationSource,
  updateSpecificationSourceRecord,
} from "../../../api/specs";
import type { PaginatedResponse } from "../../../types/common";
import type {
  CoverageStatus,
  SpecificationDetail,
  SpecificationIndexStatus,
  SpecificationListItem,
  SpecificationSourceDetail,
  SpecificationSourceListItem,
  SpecificationSourceRecord,
  SpecificationSourceType,
} from "../../../types/specs";
import CreateSpecificationSourceModal from "./CreateSpecificationSourceModal";
import DeleteSpecificationModal from "./DeleteSpecificationModal";
import SourceRecordEditModal from "./SourceRecordEditModal";
import SpecificationDetailPane from "./SpecificationDetailPane";
import SpecificationListPane from "./SpecificationListPane";
import SpecificationSourceDetailPane from "./SpecificationSourceDetailPane";
import SpecificationSourceListPane from "./SpecificationSourceListPane";

type SpecificationsMode = "sources" | "specifications";

interface ProjectSpecificationsWorkspaceProps {
  projectId: string;
  onOpenCase: (caseId: string, scenarioId: string) => void;
}

export default function ProjectSpecificationsWorkspace({
  projectId,
  onOpenCase,
}: ProjectSpecificationsWorkspaceProps) {
  const [mode, setMode] = useState<SpecificationsMode>("sources");

  const [sourcesPage, setSourcesPage] = useState<PaginatedResponse<SpecificationSourceListItem> | null>(null);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcePage, setSourcePage] = useState(1);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [sourceDetail, setSourceDetail] = useState<SpecificationSourceDetail | null>(null);
  const [sourceDetailLoading, setSourceDetailLoading] = useState(false);
  const [sourceDetailError, setSourceDetailError] = useState<string | null>(null);
  const [createSourceOpen, setCreateSourceOpen] = useState(false);
  const [recordEditTarget, setRecordEditTarget] = useState<SpecificationSourceRecord | null>(null);
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [deletingSource, setDeletingSource] = useState(false);
  const [deletingSelectedRecords, setDeletingSelectedRecords] = useState(false);
  const [recordUpdatingIds, setRecordUpdatingIds] = useState<Record<string, boolean>>({});
  const [deleteSourceOpen, setDeleteSourceOpen] = useState(false);

  const [specificationsPage, setSpecificationsPage] = useState<PaginatedResponse<SpecificationListItem> | null>(null);
  const [specificationsLoading, setSpecificationsLoading] = useState(true);
  const [specificationPage, setSpecificationPage] = useState(1);
  const [selectedSpecificationId, setSelectedSpecificationId] = useState<string | null>(null);
  const [specificationDetail, setSpecificationDetail] = useState<SpecificationDetail | null>(null);
  const [specificationDetailLoading, setSpecificationDetailLoading] = useState(false);
  const [specificationDetailError, setSpecificationDetailError] = useState<string | null>(null);
  const [deletingSpecification, setDeletingSpecification] = useState(false);
  const [deleteSpecificationOpen, setDeleteSpecificationOpen] = useState(false);
  const [specSearch, setSpecSearch] = useState("");
  const [coverageFilter, setCoverageFilter] = useState<CoverageStatus | "all">("all");
  const [sourceTypeFilter, setSourceTypeFilter] = useState<SpecificationSourceType | "all">("all");
  const [indexStatusFilter, setIndexStatusFilter] = useState<SpecificationIndexStatus | "all">("all");
  const [specSidebarWidth, setSpecSidebarWidth] = useState(360);
  const [resizing, setResizing] = useState(false);

  const loadSourcesPage = useCallback(
    async (page: number) => {
      setSourcesLoading(true);
      try {
        const nextPage = await getSpecificationSourcesPage(projectId, page);
        setSourcesPage(nextPage);
      } finally {
        setSourcesLoading(false);
      }
    },
    [projectId]
  );

  const loadSpecificationsPage = useCallback(
    async (page: number) => {
      setSpecificationsLoading(true);
      try {
        const nextPage = await getSpecificationsPage(projectId, page);
        setSpecificationsPage(nextPage);
      } finally {
        setSpecificationsLoading(false);
      }
    },
    [projectId]
  );

  const refreshSelectedSource = useCallback(async () => {
    if (!selectedSourceId) return;
    setSourceDetailLoading(true);
    setSourceDetailError(null);
    try {
      setSourceDetail(await getSpecificationSourceDetail(selectedSourceId));
    } catch {
      setSourceDetail(null);
      setSourceDetailError("Failed to load this source.");
    } finally {
      setSourceDetailLoading(false);
    }
  }, [selectedSourceId]);

  const refreshSelectedSpecification = useCallback(async () => {
    if (!selectedSpecificationId) return;
    setSpecificationDetailLoading(true);
    setSpecificationDetailError(null);
    try {
      setSpecificationDetail(await getSpecificationDetail(selectedSpecificationId));
    } catch {
      setSpecificationDetail(null);
      setSpecificationDetailError("Failed to load this specification.");
    } finally {
      setSpecificationDetailLoading(false);
    }
  }, [selectedSpecificationId]);

  useEffect(() => {
    void loadSourcesPage(sourcePage);
  }, [loadSourcesPage, sourcePage]);

  useEffect(() => {
    void loadSpecificationsPage(specificationPage);
  }, [loadSpecificationsPage, specificationPage]);

  useEffect(() => {
    if (!sourcesPage) return;
    if (
      sourcesPage.results.length > 0 &&
      !sourcesPage.results.some((source) => source.id === selectedSourceId)
    ) {
      setSelectedSourceId(sourcesPage.results[0].id);
      return;
    }
    if (sourcesPage.results.length === 0) {
      setSelectedSourceId(null);
      setSourceDetail(null);
    }
  }, [selectedSourceId, sourcesPage]);

  useEffect(() => {
    if (!specificationsPage) return;
    if (
      specificationsPage.results.length > 0 &&
      !specificationsPage.results.some((specification) => specification.id === selectedSpecificationId)
    ) {
      setSelectedSpecificationId(specificationsPage.results[0].id);
      return;
    }
    if (specificationsPage.results.length === 0) {
      setSelectedSpecificationId(null);
      setSpecificationDetail(null);
    }
  }, [selectedSpecificationId, specificationsPage]);

  useEffect(() => {
    void refreshSelectedSource();
  }, [refreshSelectedSource]);

  useEffect(() => {
    void refreshSelectedSpecification();
  }, [refreshSelectedSpecification]);

  useEffect(() => {
    if (!resizing) return;

    function handleMouseMove(event: MouseEvent) {
      setSpecSidebarWidth(Math.min(Math.max(event.clientX, 260), 560));
    }

    function handleMouseUp() {
      setResizing(false);
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [resizing]);

  async function handleParseSource() {
    if (!selectedSourceId) return;
    setParsing(true);
    try {
      const detail = await parseSpecificationSource(selectedSourceId);
      setSourceDetail(detail);
      await loadSourcesPage(sourcePage);
    } catch {
      setSourceDetailError("Could not parse this source.");
    } finally {
      setParsing(false);
    }
  }

  async function handleImportSource() {
    if (!selectedSourceId) return;
    setImporting(true);
    try {
      await importSpecificationSource(selectedSourceId);
      await Promise.all([
        refreshSelectedSource(),
        loadSourcesPage(sourcePage),
        loadSpecificationsPage(specificationPage),
      ]);
    } catch {
      setSourceDetailError("Could not import selected records from this source.");
    } finally {
      setImporting(false);
    }
  }

  async function handleDeleteSelectedRecords() {
    if (!selectedSourceId) return;
    setDeletingSelectedRecords(true);
    try {
      await deleteSelectedSpecificationSourceRecords(selectedSourceId);
      await Promise.all([refreshSelectedSource(), loadSourcesPage(sourcePage)]);
    } catch {
      setSourceDetailError("Could not delete selected source records.");
    } finally {
      setDeletingSelectedRecords(false);
    }
  }

  async function handleToggleRecordSelection(
    record: SpecificationSourceRecord,
    selected: boolean
  ) {
    if (!selectedSourceId) return;

    setRecordUpdatingIds((current) => ({ ...current, [record.id]: true }));
    setSourceDetail((current) =>
      current
        ? {
            ...current,
            records: current.records.map((item) =>
              item.id === record.id ? { ...item, is_selected: selected } : item
            ),
          }
        : current
    );

    try {
      await updateSpecificationSourceRecord(selectedSourceId, record.id, {
        is_selected: selected,
      });
      await Promise.all([refreshSelectedSource(), loadSourcesPage(sourcePage)]);
    } catch {
      setSourceDetailError("Could not update this source record selection.");
      await refreshSelectedSource();
    } finally {
      setRecordUpdatingIds((current) => {
        const next = { ...current };
        delete next[record.id];
        return next;
      });
    }
  }

  async function handleDeleteSource() {
    if (!selectedSourceId) return;
    setDeletingSource(true);
    try {
      await deleteSpecificationSource(selectedSourceId);
      setSelectedSourceId(null);
      setSourceDetail(null);
      await loadSourcesPage(sourcePage);
    } catch {
      setSourceDetailError("Could not delete this source.");
    } finally {
      setDeletingSource(false);
    }
  }

  async function handleDeleteSpecification() {
    if (!selectedSpecificationId) return;
    setDeletingSpecification(true);
    try {
      await deleteSpecification(selectedSpecificationId);
      setDeleteSpecificationOpen(false);
      setSelectedSpecificationId(null);
      setSpecificationDetail(null);
      await loadSpecificationsPage(specificationPage);
    } catch {
      setSpecificationDetailError("Could not delete this specification.");
    } finally {
      setDeletingSpecification(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          {(["sources", "specifications"] as SpecificationsMode[]).map((value) => (
            <button
              key={value}
              onClick={() => setMode(value)}
              className={[
                "rounded-md px-3 py-1.5 text-sm font-medium transition",
                mode === value
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
              ].join(" ")}
            >
              {value === "sources" ? "Sources" : "Imported Specs"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {mode === "sources" ? (
          <>
            <SpecificationSourceListPane
              page={sourcePage}
              data={sourcesPage}
              loading={sourcesLoading}
              selectedSourceId={selectedSourceId}
              style={{ width: `${specSidebarWidth}px` }}
              onSelect={setSelectedSourceId}
              onCreate={() => setCreateSourceOpen(true)}
              onNext={() => setSourcePage((page) => page + 1)}
              onPrevious={() => setSourcePage((page) => Math.max(1, page - 1))}
            />
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize specifications panels"
              onMouseDown={() => setResizing(true)}
              className={`relative w-1 shrink-0 cursor-col-resize bg-slate-200 transition hover:bg-blue-400 ${
                resizing ? "bg-blue-500" : ""
              }`}
            >
              <div className="absolute inset-y-0 left-1/2 w-3 -translate-x-1/2" />
            </div>
            <main className="min-w-0 flex-1">
              <SpecificationSourceDetailPane
                detail={sourceDetail}
                loading={sourceDetailLoading}
                error={sourceDetailError}
                parsing={parsing}
                importing={importing}
                deleting={deletingSource}
                deletingSelectedRecords={deletingSelectedRecords}
                recordUpdatingIds={recordUpdatingIds}
                onParse={handleParseSource}
                onDelete={() => setDeleteSourceOpen(true)}
                onImportSelected={handleImportSource}
                onDeleteSelectedRecords={handleDeleteSelectedRecords}
                onEditRecord={setRecordEditTarget}
                onOpenSpec={(specId) => {
                  setSelectedSpecificationId(specId);
                  setMode("specifications");
                }}
                onToggleRecordSelection={handleToggleRecordSelection}
              />
            </main>
          </>
        ) : (
          <>
            <SpecificationListPane
              page={specificationPage}
              data={specificationsPage}
              loading={specificationsLoading}
              selectedSpecId={selectedSpecificationId}
              style={{ width: `${specSidebarWidth}px` }}
              search={specSearch}
              coverageFilter={coverageFilter}
              sourceTypeFilter={sourceTypeFilter}
              indexStatusFilter={indexStatusFilter}
              onSearchChange={setSpecSearch}
              onCoverageFilterChange={setCoverageFilter}
              onSourceTypeFilterChange={setSourceTypeFilter}
              onIndexStatusFilterChange={setIndexStatusFilter}
              onSelect={setSelectedSpecificationId}
              onDeleteSelected={() => setDeleteSpecificationOpen(true)}
              onNext={() => setSpecificationPage((page) => page + 1)}
              onPrevious={() => setSpecificationPage((page) => Math.max(1, page - 1))}
            />
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize specifications panels"
              onMouseDown={() => setResizing(true)}
              className={`relative w-1 shrink-0 cursor-col-resize bg-slate-200 transition hover:bg-blue-400 ${
                resizing ? "bg-blue-500" : ""
              }`}
            >
              <div className="absolute inset-y-0 left-1/2 w-3 -translate-x-1/2" />
            </div>
            <main className="min-w-0 flex-1">
              <SpecificationDetailPane
                detail={specificationDetail}
                loading={specificationDetailLoading}
                error={specificationDetailError}
                deleting={deletingSpecification}
                onOpenCase={onOpenCase}
                onDelete={() => setDeleteSpecificationOpen(true)}
              />
            </main>
          </>
        )}
      </div>

      <CreateSpecificationSourceModal
        open={createSourceOpen}
        projectId={projectId}
        onClose={() => setCreateSourceOpen(false)}
        onCreated={(source) => {
          setCreateSourceOpen(false);
          setMode("sources");
          setSelectedSourceId(source.id);
          setSourceDetail(source);
          setSourcePage(1);
          void loadSourcesPage(1);
        }}
      />

      <SourceRecordEditModal
        open={Boolean(recordEditTarget)}
        sourceId={selectedSourceId}
        record={recordEditTarget}
        onClose={() => setRecordEditTarget(null)}
        onSaved={async () => {
          setRecordEditTarget(null);
          await Promise.all([refreshSelectedSource(), loadSourcesPage(sourcePage)]);
        }}
      />

      <DeleteSpecificationModal
        open={deleteSourceOpen}
        title="Delete source"
        description={`Delete "${sourceDetail?.name || "this source"}" and its import workspace?`}
        deleting={deletingSource}
        onClose={() => setDeleteSourceOpen(false)}
        onConfirm={() => void handleDeleteSource()}
      />

      <DeleteSpecificationModal
        open={deleteSpecificationOpen}
        title="Delete specification"
        description={`Delete "${specificationDetail?.title || "this specification"}" from imported specs?`}
        deleting={deletingSpecification}
        onClose={() => setDeleteSpecificationOpen(false)}
        onConfirm={() => void handleDeleteSpecification()}
      />
    </div>
  );
}
