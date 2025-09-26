from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.html import format_html
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    """
    Inline admin for UserProfile
    """

    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ("bio", "location", "birth_date", "phone_number", "website", "avatar")


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
        )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User Admin
    """

    inlines = (UserProfileInline,)
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = ["email", "username", "role", "is_active", "is_staff", "created_at"]
    list_filter = ["role", "is_active", "is_staff", "created_at"]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["-created_at"]
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Role & Permissions",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important Dates",
            {"fields": ("last_login", "date_joined", "created_at", "updated_at")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "role", "password1", "password2"),
            },
        ),
    )

    readonly_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Full Name"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    UserProfile Admin
    """

    list_display = ("user", "location", "phone_number", "created_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__email", "user__username", "location", "phone_number")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Profile Information",
            {
                "fields": (
                    "bio",
                    "location",
                    "birth_date",
                    "phone_number",
                    "website",
                    "avatar",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("user",)
        return self.readonly_fields


# Customize admin site headers
admin.site.site_header = "AI Document Process Admin"
admin.site.site_title = "AI Doc Process Admin Portal"
admin.site.index_title = "Welcome to AI Document Process Administration"
