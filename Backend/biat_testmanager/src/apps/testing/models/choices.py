#src/app/testing/models/choices.py
from django.db import models


class TestScenarioType(models.TextChoices):
    HAPPY_PATH = "happy_path", "Happy Path"
    ALTERNATIVE_FLOW = "alternative_flow", "Alternative Flow"
    EDGE_CASE = "edge_case", "Edge Case"
    SECURITY = "security", "Security"
    PERFORMANCE = "performance", "Performance"
    ACCESSIBILITY = "accessibility", "Accessibility"


class TestPriority(models.TextChoices):
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class BusinessPriority(models.TextChoices):
    MUST_HAVE = "must_have", "Must Have"
    SHOULD_HAVE = "should_have", "Should Have"
    COULD_HAVE = "could_have", "Could Have"
    WONT_HAVE = "wont_have", "Won't Have"


class TestScenarioPolarity(models.TextChoices):
    POSITIVE = "positive", "Positive"
    NEGATIVE = "negative", "Negative"


class TestCaseDesignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_REVIEW = "in_review", "In Review"
    APPROVED = "approved", "Approved"
    ARCHIVED = "archived", "Archived"


TestCaseStatus = TestCaseDesignStatus


class TestCaseAutomationStatus(models.TextChoices):
    MANUAL = "manual", "Manual"
    AUTOMATED = "automated", "Automated"
    IN_PROGRESS = "in_progress", "In Progress"


class TestCaseOnFailureBehavior(models.TextChoices):
    FAIL_AND_STOP = "fail_and_stop", "Fail And Stop"
    FAIL_BUT_CONTINUE = "fail_but_continue", "Fail But Continue"


LEGACY_TEST_CASE_STATUS_TO_DESIGN_STATUS = {
    "draft": TestCaseDesignStatus.DRAFT,
    "ready": TestCaseDesignStatus.APPROVED,
    "running": TestCaseDesignStatus.APPROVED,
    "passed": TestCaseDesignStatus.APPROVED,
    "failed": TestCaseDesignStatus.APPROVED,
    "skipped": TestCaseDesignStatus.APPROVED,
    TestCaseDesignStatus.DRAFT: TestCaseDesignStatus.DRAFT,
    TestCaseDesignStatus.IN_REVIEW: TestCaseDesignStatus.IN_REVIEW,
    TestCaseDesignStatus.APPROVED: TestCaseDesignStatus.APPROVED,
    TestCaseDesignStatus.ARCHIVED: TestCaseDesignStatus.ARCHIVED,
}


def map_legacy_test_case_status_to_design_status(value: str | None) -> str:
    return LEGACY_TEST_CASE_STATUS_TO_DESIGN_STATUS.get(
        value or "",
        TestCaseDesignStatus.DRAFT,
    )


class TestPlanStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class TestRunTriggerType(models.TextChoices):
    MANUAL = "manual", "Manual"
    CI_CD = "ci_cd", "CI/CD"
    SCHEDULED = "scheduled", "Scheduled"
    WEBHOOK = "webhook", "Webhook"


class TestRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class TestRunKind(models.TextChoices):
    PLANNED = "planned", "Planned"
    STANDALONE = "standalone", "Standalone"
    SYSTEM_GENERATED = "system_generated", "System Generated"


class TestRunCaseStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    ERROR = "error", "Error"
    CANCELLED = "cancelled", "Cancelled"

