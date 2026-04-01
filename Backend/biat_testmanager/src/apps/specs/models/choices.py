from django.db import models


class SpecificationSourceType(models.TextChoices):
    MANUAL = "manual", "Manual"
    PLAIN_TEXT = "plain_text", "Plain Text"
    CSV = "csv", "CSV"
    XLSX = "xlsx", "XLSX"
    PDF = "pdf", "PDF"
    DOCX = "docx", "DOCX"
    JIRA_ISSUE = "jira_issue", "Jira Issue"
    FILE_UPLOAD = "file_upload", "File Upload"
    URL = "url", "URL"


class SpecChunkType(models.TextChoices):
    FUNCTIONAL_REQUIREMENT = "functional_requirement", "Functional Requirement"
    ACCEPTANCE_CRITERIA = "acceptance_criteria", "Acceptance Criteria"
    USER_STORY = "user_story", "User Story"
    OTHER = "other", "Other"


class SpecificationSourceParserStatus(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    PARSING = "parsing", "Parsing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"
    IMPORTED = "imported", "Imported"


class SpecificationSourceRecordStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IMPORTED = "imported", "Imported"
    SKIPPED = "skipped", "Skipped"
    FAILED = "failed", "Failed"
