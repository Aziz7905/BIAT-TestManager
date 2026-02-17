import uuid
import re

from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    QA_LEAD = "QA_LEAD", "QA Lead"
    TESTER = "TESTER", "Tester"


matricule_validator = RegexValidator(
    regex=r"^\d{4}$",
    message="Matricule must be exactly 4 digits (e.g., 0123).",
)


def normalize_part(s: str) -> str:
    s = (s or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


class UserManager(BaseUserManager):
    def create_user(self, matricule: str, first_name: str, last_name: str, password=None, **extra_fields):
        if not matricule:
            raise ValueError("Matricule is required.")
        if not first_name:
            raise ValueError("First name is required.")
        if not last_name:
            raise ValueError("Last name is required.")

        user = self.model(
            matricule=matricule,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            **extra_fields,
        )
        
        if password:
            user.set_password(password)
        
        user.save(using=self._db)
        return user

    def create_superuser(self, matricule: str, first_name: str, last_name: str, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.ADMIN)

        return self.create_user(matricule, first_name, last_name, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    matricule = models.CharField(max_length=4, unique=True, validators=[matricule_validator])
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.TESTER)
    department = models.CharField(max_length=120, blank=True)

    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "matricule"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "accounts_user"

    def __str__(self):
        return f"{self.matricule} - {self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        self.email = f"{normalize_part(self.first_name)}.{normalize_part(self.last_name)}@biat-it.tn"
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        expected = f"{normalize_part(self.first_name)}.{normalize_part(self.last_name)}@biat-it.tn"
        if self.email and self.email.lower() != expected:
            raise ValidationError({"email": f"Email must be exactly: {expected}"})