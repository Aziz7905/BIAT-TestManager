import json
import uuid

from django.db import models
from encrypted_model_fields.fields import EncryptedTextField


class UserIntegrationCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_profile = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="integration_credentials",
    )
    provider = models.ForeignKey(
        "integrations.IntegrationProvider",
        to_field="slug",
        on_delete=models.PROTECT,
        related_name="user_credentials",
    )
    credential_json_encrypted = EncryptedTextField(default="{}", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_user_integration_credential"
        ordering = ["user_profile__user__username", "provider"]
        unique_together = [("user_profile", "provider")]

    def __str__(self) -> str:
        return f"{self.user_profile.user.username} / {self.provider_id}"

    @property
    def credential_data(self) -> dict:
        if not self.credential_json_encrypted:
            return {}
        try:
            parsed_value = json.loads(self.credential_json_encrypted)
        except json.JSONDecodeError:
            return {}
        return parsed_value if isinstance(parsed_value, dict) else {}

    def set_credential_data(self, payload: dict) -> None:
        self.credential_json_encrypted = json.dumps(payload or {})
