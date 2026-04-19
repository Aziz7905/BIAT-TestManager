import uuid

from xml.etree.ElementTree import Element, SubElement, tostring

from django.db import models

from apps.automation.models.choices import TestResultStatus


class TestResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.OneToOneField(
        "automation.TestExecution",
        on_delete=models.CASCADE,
        related_name="result",
    )
    status = models.CharField(max_length=20, choices=TestResultStatus.choices)
    duration_ms = models.IntegerField(default=0)
    total_steps = models.IntegerField(default=0)
    passed_steps = models.IntegerField(default=0)
    failed_steps = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    stack_trace = models.TextField(null=True, blank=True)
    junit_xml = models.TextField(null=True, blank=True)
    video_url = models.URLField(null=True, blank=True)
    artifacts_path = models.FileField(
        upload_to="automation/artifacts/%Y/%m/%d",
        null=True,
        blank=True,
    )
    ai_failure_analysis = models.TextField(null=True, blank=True)
    issues_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "automation_test_result"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.execution_id} / {self.status}"

    def export_junit_xml(self) -> str:
        if self.junit_xml:
            return self.junit_xml

        testsuite = Element(
            "testsuite",
            name=self.execution.test_case.title,
            tests="1",
            failures="1" if self.status == TestResultStatus.FAILED else "0",
            errors="1" if self.status == TestResultStatus.ERROR else "0",
            skipped="1" if self.status == TestResultStatus.SKIPPED else "0",
            time=f"{self.duration_ms / 1000:.3f}",
        )
        testcase = SubElement(
            testsuite,
            "testcase",
            classname=self.execution.test_case.scenario.suite.name,
            name=self.execution.test_case.title,
            time=f"{self.duration_ms / 1000:.3f}",
        )

        if self.status == TestResultStatus.FAILED:
            failure = SubElement(testcase, "failure", message=self.error_message or "Failed")
            failure.text = self.stack_trace or self.error_message or "Execution failed."
        elif self.status == TestResultStatus.ERROR:
            error = SubElement(testcase, "error", message=self.error_message or "Error")
            error.text = self.stack_trace or self.error_message or "Execution errored."
        elif self.status == TestResultStatus.SKIPPED:
            SubElement(testcase, "skipped")

        self.junit_xml = tostring(testsuite, encoding="unicode")
        self.save(update_fields=["junit_xml"])
        return self.junit_xml

    def get_artifacts(self) -> dict:
        from apps.automation.services.artifacts import get_result_artifacts

        return get_result_artifacts(self)
