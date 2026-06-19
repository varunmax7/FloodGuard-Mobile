"""
accounts/models.py — User, SavedPlace models (stub for Phase 0).
Full implementation in Phase 5.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.gis.db import models


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required")
        user = self.model(phone=phone, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if password:
            user = self.model(phone=phone, **extra_fields)
            user.set_password(password)
            user.save(using=self._db)
            return user
        return self.create_user(phone, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model — phone-based, no username/email."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)
    fcm_token = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.phone


class SavedPlace(models.Model):
    """User-saved locations for personalised alerts."""
    LABEL_CHOICES = [("HOME", "Home"), ("OFFICE", "Office"), ("OTHER", "Other")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_places")
    label = models.CharField(max_length=10, choices=LABEL_CHOICES)
    geom = models.PointField(srid=4326)
    hex = models.ForeignKey(
        "geo.HexCell", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="saved_places",
    )
    notify = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_saved_place"
        verbose_name = "Saved Place"
        verbose_name_plural = "Saved Places"

    def __str__(self):
        return f"{self.user.phone} — {self.label}"
