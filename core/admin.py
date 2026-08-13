from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Activity, ClassSession, SessionEnrollment, StudentResult, User


@admin.register(User)
class LearnLoopUserAdmin(UserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")} ),
        ("Profile", {"fields": ("first_name", "last_name", "role")} ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
        ("Important dates", {"fields": ("last_login", "date_joined")} ),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")} ),)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_public", "question_total", "updated_at")
    list_filter = ("is_public", "author")
    search_fields = ("title", "description", "author__email")

    @admin.display(description="Questions")
    def question_total(self, obj):
        return obj.question_count


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ("join_code", "activity", "teacher", "is_active", "started_at")
    list_filter = ("is_active",)
    search_fields = ("join_code", "activity__title", "teacher__email")


@admin.register(SessionEnrollment)
class SessionEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "joined_at")
    search_fields = ("student__email", "session__join_code", "session__activity__title")


@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ("student", "activity", "score", "total_questions", "date_completed")
    list_filter = ("activity",)
    search_fields = ("student__email", "activity__title")
