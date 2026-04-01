import uuid

from django.db import models

from .choices import SpecificationSourceRecordStatus


class SpecificationSourceRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        "specs.SpecificationSource",
        on_delete=models.CASCADE,
        related_name="records",
    )
    record_index = models.IntegerField()
    external_reference = models.CharField(max_length=120, blank=True)
    section_label = models.CharField(max_length=200, blank=True)
    row_number = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=300)
    content = models.TextField()
    record_metadata = models.JSONField(default=dict, blank=True)
    is_selected = models.BooleanField(default=True)
    import_status = models.CharField(
        max_length=20,
        choices=SpecificationSourceRecordStatus.choices,
        default=SpecificationSourceRecordStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    linked_specification = models.OneToOneField(
        "specs.Specification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specs_specification_source_record"
        ordering = ["source__name", "record_index"]
        unique_together = [("source", "record_index")]

    def __str__(self) -> str:
        return f"{self.source.name} / Record {self.record_index + 1}"
