"""Domain models for LearnLoop's activities and live classrooms."""

from __future__ import annotations

import secrets
import string
import uuid
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


def default_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "intro",
            "title": "Welcome to your activity",
            "body": "Add a short introduction to guide your learners.",
        },
        {
            "type": "question",
            "prompt": "What is one thing you are hoping to learn?",
            "options": ["A new idea", "A new skill", "A new perspective", "All of the above"],
            "answer": 3,
            "explanation": "Every good learning journey starts with curiosity.",
        },
    ]


class EmailUserManager(BaseUserManager):
    """User manager for an email-first, username-free account model."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("The email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.STUDENT)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.TEACHER)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    objects = EmailUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:
        return self.get_full_name() or self.email


def validate_blocks(value: Any) -> None:
    """Validate the small JSON block schema used by the activity builder."""
    if not isinstance(value, list):
        raise ValidationError("Activity content must be a list of blocks.")
    if not value:
        raise ValidationError("Add at least one content block to the activity.")

    accepted_types = {"intro", "question", "image", "video", "resource"}
    for index, block in enumerate(value, start=1):
        if not isinstance(block, dict):
            raise ValidationError(f"Block {index} must be an object.")
        block_type = block.get("type")
        if block_type not in accepted_types:
            raise ValidationError(f"Block {index} has an unsupported type.")
        if block_type == "question":
            prompt = str(block.get("prompt", "")).strip()
            options = block.get("options")
            answer = block.get("answer")
            if not prompt:
                raise ValidationError(f"Question block {index} needs a prompt.")
            if not isinstance(options, list) or len(options) < 2:
                raise ValidationError(f"Question block {index} needs at least two choices.")
            if not all(isinstance(option, str) and option.strip() for option in options):
                raise ValidationError(f"Question block {index} has an empty choice.")
            if not isinstance(answer, int) or not 0 <= answer < len(options):
                raise ValidationError(f"Question block {index} needs a valid answer index.")


class Activity(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    content_json = models.JSONField(default=default_blocks, validators=[validate_blocks])
    is_public = models.BooleanField(default=False)
    estimated_minutes = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(180)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    @property
    def question_count(self) -> int:
        return sum(block.get("type") == "question" for block in self.content_json)

    @property
    def block_count(self) -> int:
        return len(self.content_json)

    def clean(self):
        super().clean()
        validate_blocks(self.content_json)
        if self.author_id and self.author.role != User.Role.TEACHER:
            raise ValidationError({"author": "Only teacher accounts can publish activities."})

    def __str__(self) -> str:
        return self.title


class ClassSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="sessions")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="class_sessions")
    join_code = models.CharField(
        max_length=6,
        unique=True,
        editable=False,
        validators=[RegexValidator(r"^[A-Z0-9]{6}$", "Use six uppercase letters or digits.")],
    )
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    @classmethod
    def generate_join_code(cls) -> str:
        alphabet = string.ascii_uppercase + string.digits
        # The database uniqueness constraint remains the final guard under
        # concurrent session creation.
        for _ in range(20):
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if not cls.objects.filter(join_code=code).exists():
                return code
        raise RuntimeError("Could not generate a unique join code. Please retry.")

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = self.generate_join_code()
        super().save(*args, **kwargs)

    def end(self) -> None:
        if self.is_active:
            self.is_active = False
            self.ended_at = timezone.now()
            self.save(update_fields=["is_active", "ended_at"])

    @property
    def is_joinable(self) -> bool:
        return self.is_active

    def clean(self):
        super().clean()
        if self.activity_id and self.teacher_id and self.activity.author_id != self.teacher_id:
            raise ValidationError("A session's teacher must own its activity.")

    def __str__(self) -> str:
        return f"{self.activity.title} — {self.join_code}"


class SessionEnrollment(models.Model):
    """A student's explicit entry to a live room after entering its code."""

    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="session_enrollments")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["session", "student"], name="unique_session_enrollment")
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student.role != User.Role.STUDENT:
            raise ValidationError({"student": "Only students can join a live session."})

    def __str__(self) -> str:
        return f"{self.student} joined {self.session}"


class StudentResult(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="results")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="results")
    session = models.ForeignKey(
        ClassSession,
        on_delete=models.SET_NULL,
        related_name="results",
        null=True,
        blank=True,
    )
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    answers_json = models.JSONField(default=dict, blank=True)
    date_completed = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_completed"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "activity", "session"],
                name="unique_student_activity_session_result",
            )
        ]

    @property
    def percentage(self) -> int:
        if not self.total_questions:
            return 0
        return round(self.score / self.total_questions * 100)

    def clean(self):
        super().clean()
        if self.student_id and self.student.role != User.Role.STUDENT:
            raise ValidationError({"student": "Only students can receive results."})
        if self.score > self.total_questions:
            raise ValidationError({"score": "Score cannot exceed the question total."})
        if self.session_id and self.session.activity_id != self.activity_id:
            raise ValidationError({"session": "This session belongs to another activity."})

    def __str__(self) -> str:
        return f"{self.student} — {self.activity} ({self.score}/{self.total_questions})"
