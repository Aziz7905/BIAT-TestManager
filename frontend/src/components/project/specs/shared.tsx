import type {
  CoverageStatus,
  SpecificationIndexStatus,
  SpecificationSourceParserStatus,
  SpecificationSourceRecordStatus,
  SpecificationSourceType,
} from "../../../types/specs";

export function sourceTypeLabel(sourceType: SpecificationSourceType) {
  switch (sourceType) {
    case "plain_text":
      return "Plain text";
    case "jira_issue":
      return "Jira issue";
    case "file_upload":
      return "File upload";
    default:
      return sourceType.toUpperCase().replace("_", " ");
  }
}

export function parserStatusColor(status: SpecificationSourceParserStatus) {
  switch (status) {
    case "ready":
      return "green";
    case "failed":
      return "red";
    case "parsing":
      return "yellow";
    case "imported":
      return "blue";
    default:
      return "slate";
  }
}

export function recordStatusColor(status: SpecificationSourceRecordStatus) {
  switch (status) {
    case "imported":
      return "green";
    case "failed":
      return "red";
    case "skipped":
      return "yellow";
    default:
      return "slate";
  }
}

export function coverageColor(status: CoverageStatus) {
  return status === "covered" ? "green" : "orange";
}

export function indexStatusColor(status: SpecificationIndexStatus) {
  switch (status) {
    case "indexed":
      return "green";
    case "failed":
      return "red";
    case "stale":
      return "yellow";
    default:
      return "slate";
  }
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "--";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function matchesSpecSearch(
  value: {
    title: string;
    external_reference: string | null;
  },
  search: string
) {
  const query = search.trim().toLowerCase();
  if (!query) return true;
  return (
    value.title.toLowerCase().includes(query) ||
    (value.external_reference ?? "").toLowerCase().includes(query)
  );
}
