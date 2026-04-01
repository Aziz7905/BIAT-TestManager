from .base import ParsedSourceRecord, ParsedSourceResult, SpecificationSourceParseError


class JiraSpecificationSourceParser:
    def parse(self, source):
        if not source.jira_issue_key:
            raise SpecificationSourceParseError("A Jira issue key is required.")

        content = source.raw_text.strip() or f"Imported Jira issue {source.jira_issue_key}"

        record = ParsedSourceRecord(
            title=source.name or source.jira_issue_key,
            content=content,
            external_reference=source.jira_issue_key,
            section_label="Jira Issue",
            record_metadata={
                "jira_issue_key": source.jira_issue_key,
                "source_url": source.source_url or "",
            },
        )

        return ParsedSourceResult(
            records=[record],
            source_metadata={
                "format": "jira_issue",
                "jira_issue_key": source.jira_issue_key,
            },
        )

