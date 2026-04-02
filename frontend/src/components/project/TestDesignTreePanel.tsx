/** Dense test-library explorer for folder, suite, scenario, and case navigation. */
import { Badge } from "../ui";
import type { TestCase, TestScenario, TestSuite } from "../../types/testing";

interface FolderGroup {
  key: string;
  label: string;
  depth: number;
  suiteCount: number;
}

interface FolderNode {
  key: string;
  label: string;
  depth: number;
  exactSuiteCount: number;
  totalSuiteCount: number;
  children: FolderNode[];
}

interface MutableFolderNode {
  key: string;
  label: string;
  depth: number;
  exactSuiteCount: number;
  totalSuiteCount: number;
  children: Map<string, MutableFolderNode>;
}

interface TestDesignTreePanelProps {
  folderGroups: FolderGroup[];
  suites: TestSuite[];
  scenarios: TestScenario[];
  cases: TestCase[];
  selectedFolder: string;
  selectedSuiteId: string;
  selectedScenarioId: string;
  selectedCaseId: string;
  onSelectFolder: (folderKey: string) => void;
  onSelectSuite: (suiteId: string) => void;
  onSelectScenario: (scenarioId: string) => void;
  onSelectCase: (caseId: string) => void;
  embedded?: boolean;
}

function getScenarioVariant(scenario: TestScenario) {
  return scenario.polarity === "positive" ? "verified" : "warm";
}

function getCaseVariant(testCase: TestCase) {
  if (testCase.status === "passed" || testCase.status === "ready") {
    return "verified";
  }

  if (testCase.status === "failed" || testCase.status === "skipped") {
    return "warm";
  }

  return "unverified";
}

function buildFolderTree(folderGroups: FolderGroup[]): FolderNode[] {
  const rootNodes = new Map<string, MutableFolderNode>();

  folderGroups.forEach((folderGroup) => {
    if (folderGroup.key === "Unfiled") {
      rootNodes.set("Unfiled", {
        key: "Unfiled",
        label: "Unfiled",
        depth: 0,
        exactSuiteCount: folderGroup.suiteCount,
        totalSuiteCount: folderGroup.suiteCount,
        children: new Map(),
      });
      return;
    }

    const segments = folderGroup.key
      .split("/")
      .map((segment) => segment.trim())
      .filter(Boolean);

    let currentMap = rootNodes;
    let currentPath = "";

    segments.forEach((segment, index) => {
      currentPath = currentPath ? `${currentPath}/${segment}` : segment;
      const existingNode = currentMap.get(currentPath);

      if (!existingNode) {
        currentMap.set(currentPath, {
          key: currentPath,
          label: segment,
          depth: index,
          exactSuiteCount: 0,
          totalSuiteCount: 0,
          children: new Map(),
        });
      }

      const node = currentMap.get(currentPath);
      if (!node) {
        return;
      }

      node.totalSuiteCount += folderGroup.suiteCount;
      if (index === segments.length - 1) {
        node.exactSuiteCount = folderGroup.suiteCount;
      }

      currentMap = node.children;
    });
  });

  const finalizeNode = (node: MutableFolderNode): FolderNode => ({
    key: node.key,
    label: node.label,
    depth: node.depth,
    exactSuiteCount: node.exactSuiteCount,
    totalSuiteCount: node.totalSuiteCount,
    children: [...node.children.values()]
      .sort((left, right) => left.label.localeCompare(right.label))
      .map(finalizeNode),
  });

  return [...rootNodes.values()]
    .sort((left, right) => {
      if (left.key === "Unfiled") {
        return 1;
      }

      if (right.key === "Unfiled") {
        return -1;
      }

      return left.label.localeCompare(right.label);
    })
    .map(finalizeNode);
}

function formatFolderLabel(node: FolderNode): string {
  if (node.depth === 0 || node.key === "Unfiled") {
    return node.label;
  }

  return node.key.replaceAll("/", " / ");
}

function getCaseMetaLabel(testCase: TestCase): string {
  if (testCase.linked_specifications.length > 0) {
    return `${testCase.linked_specifications.length} requirement${
      testCase.linked_specifications.length === 1 ? "" : "s"
    }`;
  }

  return `Version ${testCase.version}`;
}

export function TestDesignTreePanel({
  folderGroups,
  suites,
  scenarios,
  cases,
  selectedFolder,
  selectedSuiteId,
  selectedScenarioId,
  selectedCaseId,
  onSelectFolder,
  onSelectSuite,
  onSelectScenario,
  onSelectCase,
  embedded = false,
}: Readonly<TestDesignTreePanelProps>) {
  const activeFolder = selectedFolder || folderGroups[0]?.key || "";
  const folderTree = buildFolderTree(folderGroups);

  const renderFolderNode = (node: FolderNode) => {
    const isActiveFolder = activeFolder === node.key;
    const isAncestorFolder =
      activeFolder !== node.key &&
      activeFolder.startsWith(`${node.key}/`) &&
      node.key !== "Unfiled";
    const isExpanded = isActiveFolder || isAncestorFolder;
    const folderSuites = suites.filter(
      (suite) => (suite.folder_path.trim() || "Unfiled") === node.key
    );

    return (
      <div key={node.key} className="space-y-2">
        <button
          type="button"
          onClick={() => onSelectFolder(node.key)}
          className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
            isActiveFolder
              ? "border-primary-light bg-primary-light/10"
              : "border-border bg-bg hover:border-primary-light/30 hover:bg-primary-light/10"
          }`}
          style={{ paddingLeft: `${16 + node.depth * 16}px` }}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight text-text">
                {formatFolderLabel(node)}
              </p>
              <p className="mt-1 text-xs text-muted">
                {node.totalSuiteCount} suite
                {node.totalSuiteCount === 1 ? "" : "s"}
                {node.children.length > 0 ? ` / ${node.children.length} subfolder` : ""}
                {node.children.length > 1 ? "s" : ""}
              </p>
            </div>
            <Badge variant={isActiveFolder ? "verified" : "tag"}>
              {node.exactSuiteCount || node.totalSuiteCount}
            </Badge>
          </div>
        </button>

        {isExpanded ? (
          <div className="space-y-2">
            {node.children.map(renderFolderNode)}

            {isActiveFolder ? (
              <div className="space-y-2 border-l border-border/80 pl-4">
                {folderSuites.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-border bg-surface px-3 py-3 text-sm text-muted">
                    No suites are stored directly in this folder.
                  </p>
                ) : (
                  folderSuites.map((suite) => {
                    const isActiveSuite = selectedSuiteId === suite.id;

                    return (
                      <div key={suite.id} className="space-y-2">
                        <button
                          type="button"
                          onClick={() => onSelectSuite(suite.id)}
                          className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                            isActiveSuite
                              ? "border-primary bg-primary text-white"
                              : "border-border bg-surface text-text hover:border-primary-light/30 hover:bg-primary-light/10"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold tracking-tight">
                                {suite.name}
                              </p>
                              <p
                                className={`mt-1 text-xs ${
                                  isActiveSuite ? "text-white/80" : "text-muted"
                                }`}
                              >
                                {suite.scenario_count} scenarios / {suite.total_case_count} cases
                              </p>
                            </div>
                            <div className="flex flex-col items-end gap-2">
                              <Badge variant={isActiveSuite ? "automated" : "tag"}>
                                {suite.pass_rate}% pass
                              </Badge>
                              {suite.linked_specification_count > 0 ? (
                                <span
                                  className={`text-[11px] font-semibold ${
                                    isActiveSuite ? "text-white/80" : "text-muted"
                                  }`}
                                >
                                  {suite.linked_specification_count} req
                                </span>
                              ) : null}
                            </div>
                          </div>
                        </button>

                        {isActiveSuite ? (
                          <div className="space-y-2 border-l border-border/70 pl-4">
                            {scenarios.length === 0 ? (
                              <p className="rounded-2xl border border-dashed border-border bg-bg px-3 py-3 text-sm text-muted">
                                No scenarios in this suite yet.
                              </p>
                            ) : (
                              scenarios.map((scenario) => {
                                const isActiveScenario =
                                  selectedScenarioId === scenario.id;

                                return (
                                  <div key={scenario.id} className="space-y-2">
                                    <button
                                      type="button"
                                      onClick={() => onSelectScenario(scenario.id)}
                                      className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                                        isActiveScenario
                                          ? "border-primary-light bg-primary-light/10"
                                          : "border-border bg-surface hover:border-primary-light/30"
                                      }`}
                                    >
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                          <p className="truncate text-sm font-semibold text-text">
                                            {scenario.title}
                                          </p>
                                          <p className="mt-1 text-xs text-muted">
                                            {scenario.case_count} cases / {scenario.priority.replaceAll("_", " ")}
                                          </p>
                                        </div>
                                        <div className="flex flex-col items-end gap-2">
                                          <Badge variant={getScenarioVariant(scenario)}>
                                            {scenario.polarity}
                                          </Badge>
                                          {scenario.linked_specification_count > 0 ? (
                                            <span className="text-[11px] font-semibold text-muted">
                                              {scenario.linked_specification_count} req
                                            </span>
                                          ) : null}
                                        </div>
                                      </div>
                                    </button>

                                    {isActiveScenario ? (
                                      <div className="space-y-2 border-l border-border/70 pl-4">
                                        {cases.length === 0 ? (
                                          <p className="rounded-2xl border border-dashed border-border bg-bg px-3 py-3 text-sm text-muted">
                                            No cases in this scenario yet.
                                          </p>
                                        ) : (
                                          cases.map((testCase) => {
                                            const isActiveCase =
                                              selectedCaseId === testCase.id;

                                            return (
                                              <button
                                                key={testCase.id}
                                                type="button"
                                                onClick={() => onSelectCase(testCase.id)}
                                                className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                                                  isActiveCase
                                                    ? "border-primary bg-primary text-white"
                                                    : "border-border bg-surface text-text hover:border-primary-light/30 hover:bg-primary-light/10"
                                                }`}
                                              >
                                                <div className="flex items-start justify-between gap-3">
                                                  <div className="min-w-0">
                                                    <p className="truncate text-sm font-semibold">
                                                      {testCase.title}
                                                    </p>
                                                    <p
                                                      className={`mt-1 text-xs ${
                                                        isActiveCase
                                                          ? "text-white/80"
                                                          : "text-muted"
                                                      }`}
                                                    >
                                                      {getCaseMetaLabel(testCase)}
                                                    </p>
                                                  </div>
                                                  <div className="flex flex-col items-end gap-2">
                                                    <Badge
                                                      variant={
                                                        isActiveCase
                                                          ? "automated"
                                                          : getCaseVariant(testCase)
                                                      }
                                                    >
                                                      {testCase.status}
                                                    </Badge>
                                                    <span
                                                      className={`text-[11px] font-semibold ${
                                                        isActiveCase
                                                          ? "text-white/80"
                                                          : "text-muted"
                                                      }`}
                                                    >
                                                      v{testCase.version}
                                                    </span>
                                                  </div>
                                                </div>
                                              </button>
                                            );
                                          })
                                        )}
                                      </div>
                                    ) : null}
                                  </div>
                                );
                              })
                            )}
                          </div>
                        ) : null}
                      </div>
                    );
                  })
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  };

  const content = (
    <>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
        Test design tree
      </p>
      <p className="mt-2 text-sm leading-6 text-muted">
        Navigate the library as users expect it: folder, suite, scenario, then case.
      </p>

      <div className="mt-6 space-y-2">
        {folderTree.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-bg p-4 text-sm text-muted">
            No test folders or suites have been created yet.
          </div>
        ) : (
          folderTree.map(renderFolderNode)
        )}
      </div>
    </>
  );

  if (embedded) {
    return <div>{content}</div>;
  }

  return (
    <aside className="rounded-[28px] border border-border bg-surface p-5 shadow-sm">
      {content}
    </aside>
  );
}
