"""
accounts/admin.py — register User and SavedPlace in Django admin.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SavedPlace


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("phone", "is_active", "is_staff", "created_at")
    list_filter = ("is_active", "is_staff")
    search_fields = ("phone",)
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("FCM", {"fields": ("fcm_token",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "password1", "password2")}),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(SavedPlace)
class SavedPlaceAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "notify", "created_at")
    list_filter = ("label", "notify")
    search_fields = ("user__phone",)
