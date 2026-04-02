import type { Specification, SpecificationSource } from "../../types/specs";

export type SpecificationBadgeVariant =
  | "tag"
  | "unverified"
  | "verified"
  | "automated"
  | "warm"
  | "priority-high"
  | "priority-medium"
  | "priority-low";

export interface StructuredSpecificationFields {
  reference?: string;
  title?: string;
  type?: string;
  description?: string;
  actor?: string;
  preconditions?: string;
  steps?: string;
  expected_result?: string;
  priority?: string;
  version?: string;
  acceptance_criteria?: string;
  module?: string;
  section?: string;
  url?: string;
  [key: string]: string | undefined;
}

export interface SpecificationPresentation {
  identifier: string;
  typeLabel: string;
  priorityLabel: string;
  description: string;
  steps: string;
  expectedResult: string;
  preconditions: string;
  acceptanceCriteria: string;
  moduleLabel: string;
  sectionLabel: string;
  urlLabel: string;
  versionLabel: string;
  fields: StructuredSpecificationFields;
}

export interface SpecificationTraceabilityScenarioGroup {
  scenarioId: string;
  scenarioTitle: string;
  cases: Specification["linked_test_cases"];
}

export interface SpecificationTraceabilitySuiteGroup {
  suiteId: string;
  suiteName: string;
  scenarios: SpecificationTraceabilityScenarioGroup[];
}

export function labelize(value: string | null | undefined): string {
  return value ? value.replaceAll("_", " ") : "";
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  try {
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function getStatusVariant(
  status: string | null | undefined
): SpecificationBadgeVariant {
  if (status === "ready" || status === "imported") {
    return "verified";
  }

  if (status === "failed") {
    return "warm";
  }

  return "unverified";
}

export function getSourceDisplayName(
  source:
    | Pick<
        SpecificationSource,
        "name" | "file_name" | "jira_issue_key" | "source_url"
      >
    | null
    | undefined
): string | null {
  if (!source) {
    return null;
  }

  if (source.name.trim()) {
    return source.name.trim();
  }

  if (source.file_name?.trim()) {
    return source.file_name.trim();
  }

  if (source.jira_issue_key?.trim()) {
    return source.jira_issue_key.trim();
  }

  if (source.source_url?.trim()) {
    return source.source_url.trim();
  }

  return null;
}

export function getStructuredFields(
  metadata: Record<string, unknown> | undefined
): StructuredSpecificationFields {
  const recordValue = metadata?.record;
  if (!recordValue || typeof recordValue !== "object" || Array.isArray(recordValue)) {
    return {};
  }

  const structuredValue = (recordValue as Record<string, unknown>).structured_fields;
  if (
    !structuredValue ||
    typeof structuredValue !== "object" ||
    Array.isArray(structuredValue)
  ) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(structuredValue).flatMap(([key, value]) =>
      typeof value === "string" && value.trim() ? [[key, value.trim()]] : []
    )
  ) as StructuredSpecificationFields;
}

export function getSpecificationPresentation(
  specification: Specification
): SpecificationPresentation {
  const fields = getStructuredFields(specification.source_metadata);

  return {
    identifier:
      specification.external_reference ||
      specification.qtest_preview.requirement_id ||
      fields.reference ||
      specification.id.slice(0, 8),
    typeLabel: fields.type || labelize(specification.source_type) || "manual",
    priorityLabel: fields.priority || "-",
    description:
      fields.description || specification.qtest_preview.description || specification.content,
    steps: fields.steps || "",
    expectedResult:
      fields.expected_result || specification.qtest_preview.expected_result || "",
    preconditions:
      fields.preconditions || specification.qtest_preview.preconditions || "",
    acceptanceCriteria: fields.acceptance_criteria || "",
    moduleLabel: fields.module || specification.qtest_preview.module || specification.project_name,
    sectionLabel: fields.section || specification.qtest_preview.section || specification.team_name,
    urlLabel: fields.url || specification.source_url || "",
    versionLabel: fields.version || specification.version,
    fields,
  };
}

export function getSpecificationGroupLabel(specification: Specification): string {
  const fields = getStructuredFields(specification.source_metadata);

  return (
    fields.module ||
    fields.section ||
    specification.source_name ||
    specification.project_name ||
    "Ungrouped"
  );
}

export function getSpecificationGroupSubtitle(specification: Specification): string {
  const fields = getStructuredFields(specification.source_metadata);
  const details = [fields.section, fields.type, fields.priority].filter(Boolean);

  return details.join(" / ") || specification.project_name;
}

export function getPriorityVariant(
  priorityLabel: string
): SpecificationBadgeVariant {
  const normalized = priorityLabel.trim().toLowerCase();

  if (!normalized || normalized === "-") {
    return "tag";
  }

  if (
    normalized.includes("critical") ||
    normalized.includes("high") ||
    normalized.includes("must") ||
    normalized.includes("urgent")
  ) {
    return "priority-high";
  }

  if (
    normalized.includes("medium") ||
    normalized.includes("normal") ||
    normalized.includes("should")
  ) {
    return "priority-medium";
  }

  if (
    normalized.includes("low") ||
    normalized.includes("minor") ||
    normalized.includes("could") ||
    normalized.includes("won")
  ) {
    return "priority-low";
  }

  return "tag";
}

export function buildTraceabilityGroups(
  specification: Specification
): SpecificationTraceabilitySuiteGroup[] {
  const suites = new Map<
    string,
    {
      suiteId: string;
      suiteName: string;
      scenarios: Map<string, SpecificationTraceabilityScenarioGroup>;
    }
  >();

  specification.linked_test_cases.forEach((testCase) => {
    const suiteGroup =
      suites.get(testCase.suite_id) ??
      {
        suiteId: testCase.suite_id,
        suiteName: testCase.suite_name,
        scenarios: new Map(),
      };

    const scenarioGroup =
      suiteGroup.scenarios.get(testCase.scenario_id) ??
      {
        scenarioId: testCase.scenario_id,
        scenarioTitle: testCase.scenario_title,
        cases: [],
      };

    scenarioGroup.cases.push(testCase);
    suiteGroup.scenarios.set(testCase.scenario_id, scenarioGroup);
    suites.set(testCase.suite_id, suiteGroup);
  });

  return [...suites.values()]
    .map((suite) => ({
      suiteId: suite.suiteId,
      suiteName: suite.suiteName,
      scenarios: [...suite.scenarios.values()].sort((left, right) =>
        left.scenarioTitle.localeCompare(right.scenarioTitle)
      ),
    }))
    .sort((left, right) => left.suiteName.localeCompare(right.suiteName));
}
