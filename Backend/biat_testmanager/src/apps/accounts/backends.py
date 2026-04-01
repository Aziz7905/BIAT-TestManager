from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("identifier")
        if not identifier or not password:
            return None

        normalized_identifier = identifier.strip()

        try:
            user = User.objects.get(
                Q(email__iexact=normalized_identifier)
                | Q(username__iexact=normalized_identifier)
            )
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None