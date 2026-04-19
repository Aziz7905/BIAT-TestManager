from django.db import models


class IntegrationProviderSlug(models.TextChoices):
    JIRA = "jira", "Jira"
    GITHUB = "github", "GitHub"
    JENKINS = "jenkins", "Jenkins"


class WebhookEventStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSED = "processed", "Processed"
    IGNORED = "ignored", "Ignored"
    FAILED = "failed", "Failed"


class IntegrationActionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
