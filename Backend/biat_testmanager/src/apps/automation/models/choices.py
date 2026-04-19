from django.db import models


class AutomationFramework(models.TextChoices):
    PLAYWRIGHT = "playwright", "Playwright"
    SELENIUM = "selenium", "Selenium"


class AutomationLanguage(models.TextChoices):
    PYTHON = "python", "Python"
    JAVASCRIPT = "javascript", "JavaScript"
    TYPESCRIPT = "typescript", "TypeScript"
    JAVA = "java", "Java"


class AutomationScriptGeneratedBy(models.TextChoices):
    AI = "ai", "AI"
    USER = "user", "User"


class ExecutionTriggerType(models.TextChoices):
    MANUAL = "manual", "Manual"
    CI_CD = "ci_cd", "CI/CD"
    SCHEDULED = "scheduled", "Scheduled"
    WEBHOOK = "webhook", "Webhook"
    NIGHTLY = "nightly", "Nightly"


class ExecutionStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    ERROR = "error", "Error"
    CANCELLED = "cancelled", "Cancelled"


class ExecutionBrowser(models.TextChoices):
    CHROMIUM = "chromium", "Chromium"
    FIREFOX = "firefox", "Firefox"
    WEBKIT = "webkit", "WebKit"
    CHROME = "chrome", "Chrome"
    EDGE = "edge", "Edge"


class ExecutionPlatform(models.TextChoices):
    DESKTOP = "desktop", "Desktop"
    MOBILE = "mobile", "Mobile"


class ExecutionStepStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"


class ExecutionCheckpointStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RESOLVED = "resolved", "Resolved"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


class TestResultStatus(models.TextChoices):
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    ERROR = "error", "Error"


class ArtifactType(models.TextChoices):
    SCREENSHOT = "screenshot", "Screenshot"
    VIDEO = "video", "Video"
    LOG = "log", "Log"
    JUNIT_XML = "junit_xml", "JUnit XML"
    TRACE = "trace", "Trace"
