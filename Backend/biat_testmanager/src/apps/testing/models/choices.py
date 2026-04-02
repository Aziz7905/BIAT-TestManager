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


class TestCaseStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    READY = "ready", "Ready"
    RUNNING = "running", "Running"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class TestCaseAutomationStatus(models.TextChoices):
    MANUAL = "manual", "Manual"
    AUTOMATED = "automated", "Automated"
    IN_PROGRESS = "in_progress", "In Progress"


class TestCaseOnFailureBehavior(models.TextChoices):
    FAIL_AND_STOP = "fail_and_stop", "Fail And Stop"
    FAIL_BUT_CONTINUE = "fail_but_continue", "Fail But Continue"

