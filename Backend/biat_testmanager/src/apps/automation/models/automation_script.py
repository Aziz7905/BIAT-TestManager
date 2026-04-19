import difflib
import uuid

from django.db import models
from django.db.models import Max

from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
    AutomationScriptGeneratedBy,
)


class AutomationScript(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test_case = models.ForeignKey(
        "testing.TestCase",
        on_delete=models.CASCADE,
        related_name="scripts",
    )
    # Revision this script was written against. Null means "latest at time of authoring".
    test_case_revision = models.ForeignKey(
        "testing.TestCaseRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scripts",
    )
    framework = models.CharField(
        max_length=20,
        choices=AutomationFramework.choices,
    )
    language = models.CharField(
        max_length=20,
        choices=AutomationLanguage.choices,
    )
    script_content = models.TextField()
    script_version = models.IntegerField(default=1)
    generated_by = models.CharField(
        max_length=10,
        choices=AutomationScriptGeneratedBy.choices,
        default=AutomationScriptGeneratedBy.USER,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "automation_automation_script"
        ordering = ["test_case__title", "framework", "language", "-script_version"]
        unique_together = [("test_case", "framework", "language", "script_version")]

    def __str__(self) -> str:
        return (
            f"{self.test_case.title} / {self.framework} / "
            f"{self.language} / v{self.script_version}"
        )

    def save(self, *args, **kwargs):
        self._assign_version_if_needed()
        super().save(*args, **kwargs)
        if self.is_active:
            type(self).objects.filter(
                test_case=self.test_case,
                framework=self.framework,
                language=self.language,
                is_active=True,
            ).exclude(pk=self.pk).update(is_active=False)

    def _assign_version_if_needed(self):
        if not self._state.adding:
            return

        existing_version = (
            type(self).objects.filter(
                test_case=self.test_case,
                framework=self.framework,
                language=self.language,
            ).aggregate(max_version=Max("script_version"))["max_version"]
            or 0
        )
        self.script_version = existing_version + 1

    def validate_syntax(self) -> dict:
        from apps.automation.services.script_validation import validate_script_content

        return validate_script_content(
            framework=self.framework,
            language=self.language,
            script_content=self.script_content,
        )

    def get_history(self):
        return type(self).objects.filter(
            test_case=self.test_case,
            framework=self.framework,
            language=self.language,
        ).order_by("-script_version", "-created_at")

    def diff_with_previous(self) -> str:
        previous_script = (
            self.get_history().exclude(pk=self.pk).first()
        )
        if previous_script is None:
            return ""

        diff = difflib.unified_diff(
            previous_script.script_content.splitlines(),
            self.script_content.splitlines(),
            fromfile=f"v{previous_script.script_version}",
            tofile=f"v{self.script_version}",
            lineterm="",
        )
        return "\n".join(diff)
