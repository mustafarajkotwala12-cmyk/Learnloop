"""Forms shared by public, teacher, and student experiences."""

from __future__ import annotations

import json

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Activity, ClassSession, StudentResult, User, validate_blocks


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}))
    role = forms.ChoiceField(choices=User.Role.choices, widget=forms.RadioSelect, initial=User.Role.STUDENT)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email", "role", "password1", "password2")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name", "placeholder": "Last name"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account already exists for this email address.")
        return email


class EmailLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Password"}))


class ActivityForm(forms.ModelForm):
    """Metadata form plus a hidden JSON payload maintained by the JS builder."""

    content_json = forms.CharField(widget=forms.HiddenInput(), required=True)
    estimated_minutes = forms.IntegerField(required=False, initial=10, min_value=1, max_value=180)

    class Meta:
        model = Activity
        fields = ("title", "description", "estimated_minutes", "is_public")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. The solar system in 10 minutes"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Set the scene for learners…"}),
            "estimated_minutes": forms.NumberInput(attrs={"min": 1, "max": 180}),
            "is_public": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["content_json"] = json.dumps(self.instance.content_json)
        elif not self.is_bound:
            self.initial["content_json"] = json.dumps(Activity._meta.get_field("content_json").get_default())

    def clean_content_json(self):
        raw = self.cleaned_data["content_json"]
        try:
            blocks = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValidationError("The activity content could not be read. Please try again.") from exc
        try:
            validate_blocks(blocks)
        except ValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return blocks

    def clean_estimated_minutes(self):
        return self.cleaned_data.get("estimated_minutes") or 10

    def save(self, commit=True):
        activity = super().save(commit=False)
        activity.content_json = self.cleaned_data["content_json"]
        if commit:
            activity.save()
        return activity


class JoinSessionForm(forms.Form):
    join_code = forms.CharField(
        min_length=6,
        max_length=6,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "ABC123",
                "autocomplete": "off",
                "autocapitalize": "characters",
                "maxlength": "6",
            }
        ),
    )

    def clean_join_code(self):
        code = self.cleaned_data["join_code"].upper()
        if not code.isalnum() or len(code) != 6:
            raise ValidationError("Enter the six-character code from your teacher.")
        return code


class ManualGradeForm(forms.ModelForm):
    """Teacher-only fallback for entering an offline result."""

    class Meta:
        model = StudentResult
        fields = ("student", "activity", "score", "total_questions")
        widgets = {
            "score": forms.NumberInput(attrs={"min": 0}),
            "total_questions": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, teacher: User, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        self.fields["student"].queryset = User.objects.filter(role=User.Role.STUDENT).order_by("email")
        self.fields["activity"].queryset = Activity.objects.filter(author=teacher).order_by("title")

    def clean(self):
        cleaned = super().clean()
        activity = cleaned.get("activity")
        score = cleaned.get("score")
        total = cleaned.get("total_questions")
        if activity and activity.author_id != self.teacher.id:
            self.add_error("activity", "You can only grade your own activities.")
        if score is not None and total is not None and score > total:
            self.add_error("score", "Score cannot be higher than the question total.")
        return cleaned


class SessionEndForm(forms.Form):
    """Intentional form type for ending a live session."""

    confirm = forms.BooleanField(required=False)
