import uuid

from django.conf import settings
from django.db import models


class AIGenerationSessionStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    GENERATING = "generating", "Generating"
    READY_FOR_REVIEW = "ready_for_review", "Ready For Review"
    REVIEWING = "reviewing", "Reviewing"
    SAVED = "saved", "Saved"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class AIGenerationSourceType(models.TextChoices):
    PROMPT = "prompt", "Prompt"
    SPECIFICATION = "specification", "Specification"
    JIRA = "jira", "Jira"
    MANUAL = "manual", "Manual"
    MIXED = "mixed", "Mixed"


class AIGenerationContextType(models.TextChoices):
    SPEC_CHUNK = "spec_chunk", "Spec Chunk"
    TEST_SUITE = "test_suite", "Test Suite"
    TEST_SCENARIO = "test_scenario", "Test Scenario"
    TEST_CASE = "test_case", "Test Case"
    REPOSITORY_MEMORY = "repository_memory", "Repository Memory"
    JIRA = "jira", "Jira"
    GITHUB = "github", "Github"
    PROMPT = "prompt", "Prompt"


class AIGenerationSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.CASCADE,
        related_name="ai_generation_sessions",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="ai_generation_sessions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_sessions",
    )
    target_suite = models.ForeignKey(
        "testing.TestSuite",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_sessions",
    )
    target_section = models.ForeignKey(
        "testing.TestSection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_sessions",
    )
    attached_specification = models.ForeignKey(
        "specs.Specification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_generation_sessions",
    )
    status = models.CharField(
        max_length=30,
        choices=AIGenerationSessionStatus.choices,
        default=AIGenerationSessionStatus.QUEUED,
        db_index=True,
    )
    source_type = models.CharField(
        max_length=30,
        choices=AIGenerationSourceType.choices,
        default=AIGenerationSourceType.PROMPT,
    )
    objective = models.TextField()
    source_refs = models.JSONField(default=dict, blank=True)
    jira_issue_key = models.CharField(max_length=100, blank=True)
    provider_name = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=150, blank=True)
    purpose = models.CharField(max_length=30, blank=True, default="test_design")
    prompt_version = models.CharField(max_length=80, blank=True)
    schema_version = models.CharField(max_length=80, blank=True)
    draft_payload = models.JSONField(default=dict, blank=True)
    critic_report = models.JSONField(default=dict, blank=True)
    review_decisions = models.JSONField(default=dict, blank=True)
    saved_object_ids = models.JSONField(default=dict, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    mlflow_run_id = models.CharField(max_length=255, blank=True)
    trace_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_generation_session"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "status"], name="ai_gen_team_status_idx"),
            models.Index(fields=["project", "created_at"], name="ai_gen_project_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.status} / {self.objective[:60]}"


class AIGenerationRetrievedContext(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        AIGenerationSession,
        on_delete=models.CASCADE,
        related_name="retrieved_contexts",
    )
    context_type = models.CharField(
        max_length=40,
        choices=AIGenerationContextType.choices,
    )
    object_id = models.CharField(max_length=64, blank=True)
    external_ref = models.CharField(max_length=255, blank=True)
    score = models.FloatField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_generation_retrieved_context"
        ordering = ["session_id", "context_type", "-score", "created_at"]
        indexes = [
            models.Index(fields=["session", "context_type"], name="ai_ctx_session_type_idx"),
            models.Index(fields=["context_type", "object_id"], name="ai_ctx_object_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} / {self.context_type} / {self.object_id or self.external_ref}"
