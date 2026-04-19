#src/app/testing/models/test_section.py
import uuid

from django.db import models
from django.db.models import Q, UniqueConstraint


class TestSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    suite = models.ForeignKey(
        "testing.TestSuite",
        on_delete=models.CASCADE,
        related_name="sections",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    name = models.CharField(max_length=300)
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "testing_test_section"
        ordering = ["suite__name", "order_index", "name"]
        constraints = [
            UniqueConstraint(
                fields=["suite", "name"],
                condition=Q(parent__isnull=True),
                name="unique_root_section_per_suite",
            ),
            UniqueConstraint(
                fields=["suite", "parent", "name"],
                condition=Q(parent__isnull=False),
                name="unique_child_section_per_parent",
            ),
        ]

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.suite.name} / {self.parent.name} / {self.name}"
        return f"{self.suite.name} / {self.name}"

    @property
    def project(self):
        return self.suite.project

    def get_scenarios(self):
        return self.scenarios.order_by("order_index", "title")

    def get_total_cases(self) -> int:
        return self.scenarios.aggregate(total=models.Count("cases", distinct=True))["total"] or 0
