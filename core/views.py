"""Views for the public site and role-specific learning portals."""

from __future__ import annotations

import json
from typing import Any

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .decorators import student_required, teacher_required
from .forms import ActivityForm, EmailLoginForm, JoinSessionForm, ManualGradeForm, RegistrationForm
from .models import Activity, ClassSession, SessionEnrollment, StudentResult, User


def _safe_next(request: HttpRequest, default: str) -> str:
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(candidate, {request.get_host()}):
        return candidate
    return default


def _is_json_request(request: HttpRequest) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")


def _average_percentage(results) -> int | None:
    """Return a human-readable average while respecting quiz lengths."""
    values = [result.percentage for result in results if result.total_questions]
    return round(sum(values) / len(values)) if values else None


def _google_login_url() -> str | None:
    """Only show Google sign-in when a site-bound SocialApp is configured."""
    try:
        from allauth.socialaccount.models import SocialApp

        if SocialApp.objects.filter(provider="google", sites__id=settings.SITE_ID).exists():
            return reverse("google_login")
    except Exception:  # Database may not be migrated on a freshly unpacked app.
        return None
    return None


@require_GET
def landing(request: HttpRequest) -> HttpResponse:
    activities = Activity.objects.filter(is_public=True).select_related("author")[:3]
    return render(
        request,
        "core/landing.html",
        {
            "featured_activities": activities,
            "teacher_count": User.objects.filter(role=User.Role.TEACHER).count(),
            "activity_count": Activity.objects.filter(is_public=True).count(),
        },
    )


@require_GET
def browse(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()
    activities = Activity.objects.filter(is_public=True).select_related("author")
    if query:
        activities = activities.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(author__first_name__icontains=query)
        )
    return render(request, "core/browse.html", {"activities": activities, "query": query})


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("portal_redirect")
    form = EmailLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect(_safe_next(request, reverse("portal_redirect")))
        form.add_error(None, "We couldn't find an account with those details.")
    return render(
        request,
        "core/login.html",
        {
            "form": form,
            "mode": "login",
            "next": request.GET.get("next", ""),
            "google_login_url": _google_login_url(),
        },
    )


@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("portal_redirect")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # A direct sign-up has not passed through authenticate(), and this app
        # intentionally has Django plus django-allauth authentication backends.
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your LearnLoop account is ready.")
        return redirect("portal_redirect")
    return render(
        request,
        "core/login.html",
        {"form": form, "mode": "register", "google_login_url": _google_login_url()},
    )


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("landing")


def portal_redirect(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.role == User.Role.TEACHER:
        return redirect("teacher_dashboard")
    return redirect("student_dashboard")


@teacher_required
@require_GET
def teacher_dashboard(request: HttpRequest) -> HttpResponse:
    activities = (
        Activity.objects.filter(author=request.user)
        .annotate(result_count=Count("results", distinct=True), average_score=Avg("results__score"))
        .order_by("-updated_at")
    )
    active_sessions = ClassSession.objects.filter(teacher=request.user, is_active=True).select_related("activity")
    recent_sessions = ClassSession.objects.filter(teacher=request.user).select_related("activity")[:4]
    results = list(
        StudentResult.objects.filter(activity__author=request.user)
        .select_related("student", "activity")
        .order_by("-date_completed")
    )
    return render(
        request,
        "core/teacher_dashboard.html",
        {
            "activities": activities,
            "active_sessions": active_sessions,
            "recent_sessions": recent_sessions,
            "recent_results": results[:3],
            "activity_count": activities.count(),
            "active_session_count": active_sessions.count(),
            "session_count": active_sessions.count(),
            "result_count": len(results),
            "average_score": _average_percentage(results),
            "greeting": "to see you",
        },
    )


@teacher_required
@require_http_methods(["GET", "POST"])
def activity_create(request: HttpRequest) -> HttpResponse:
    form = ActivityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.author = request.user
        activity.full_clean()
        activity.save()
        messages.success(request, f'“{activity.title}” is ready for learners.')
        return redirect("teacher_dashboard")
    return render(request, "core/activity_form.html", {"form": form, "activity": None})


@teacher_required
@require_http_methods(["GET", "POST"])
def activity_edit(request: HttpRequest, activity_id: int) -> HttpResponse:
    activity = get_object_or_404(Activity, pk=activity_id, author=request.user)
    form = ActivityForm(request.POST or None, instance=activity)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.author = request.user
        activity.full_clean()
        activity.save()
        messages.success(request, "Your activity changes are live.")
        return redirect("teacher_dashboard")
    return render(request, "core/activity_form.html", {"form": form, "activity": activity})


@teacher_required
@require_POST
def teacher_start_session(request: HttpRequest, activity_id: int) -> HttpResponse:
    activity = get_object_or_404(Activity, pk=activity_id, author=request.user)
    # End any existing live session for the same activity, so every launch has
    # one unambiguous code and fresh result set.
    ClassSession.objects.filter(activity=activity, teacher=request.user, is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    session = ClassSession.objects.create(activity=activity, teacher=request.user)
    messages.success(request, f"Live session started. Share code {session.join_code}.")
    return redirect("teacher_session", session_id=session.id)


@teacher_required
@require_http_methods(["GET", "POST"])
def teacher_session(request: HttpRequest, session_id) -> HttpResponse:
    session = get_object_or_404(
        ClassSession.objects.select_related("activity"), pk=session_id, teacher=request.user
    )
    if request.method == "POST":
        session.end()
        messages.info(request, "The live session has ended. Results are saved in Class evaluation.")
        return redirect("teacher_evaluation")
    recent_results = session.results.select_related("student").order_by("-date_completed")[:10]
    return render(
        request,
        "core/session.html",
        {
            "session": session,
            "activity": session.activity,
            "recent_results": recent_results,
            "completion_count": session.results.count(),
            "participant_count": session.enrollments.count(),
            "response_count": session.results.count(),
        },
    )


@teacher_required
@require_http_methods(["GET", "POST"])
def teacher_evaluation(request: HttpRequest) -> HttpResponse:
    results = list(
        StudentResult.objects.filter(activity__author=request.user)
        .select_related("student", "activity", "session")
        .order_by("-date_completed")
    )
    form = ManualGradeForm(request.POST or None, teacher=request.user)
    if request.method == "POST" and form.is_valid():
        result = form.save(commit=False)
        # A manually entered score is the standalone record for that student/activity.
        existing = StudentResult.objects.filter(student=result.student, activity=result.activity, session__isnull=True).first()
        if existing:
            existing.score = result.score
            existing.total_questions = result.total_questions
            existing.answers_json = {"source": "manual"}
            existing.save(update_fields=["score", "total_questions", "answers_json"])
        else:
            result.answers_json = {"source": "manual"}
            result.full_clean()
            result.save()
        messages.success(request, "Grade saved.")
        return redirect("teacher_evaluation")

    activity_stats = (
        Activity.objects.filter(author=request.user)
        .annotate(completion_count=Count("results"), average_score=Avg("results__score"))
        .order_by("title")
    )
    return render(
        request,
        "core/evaluation.html",
        {
            "form": form,
            "grade_form": form,
            "results": results[:30],
            "activity_stats": activity_stats,
            "result_count": len(results),
            "completed_count": len(results),
            "activity_count": activity_stats.count(),
            "average_score": _average_percentage(results),
            "score_change": None,
        },
    )


@student_required
@require_GET
def student_dashboard(request: HttpRequest) -> HttpResponse:
    results = list(StudentResult.objects.filter(student=request.user).select_related("activity"))
    activities = Activity.objects.filter(is_public=True).select_related("author")[:4]
    live_sessions = ClassSession.objects.filter(is_active=True).select_related("activity", "teacher")[:4]
    return render(
        request,
        "core/student_dashboard.html",
        {
            "activities": activities,
            "live_sessions": live_sessions,
            "recent_results": results[:5],
            "completed_count": len(results),
            "average_score": _average_percentage(results),
            "join_form": JoinSessionForm(),
        },
    )


@student_required
@require_GET
def student_activities(request: HttpRequest) -> HttpResponse:
    activities = Activity.objects.filter(is_public=True).select_related("author")
    completed_ids = set(StudentResult.objects.filter(student=request.user).values_list("activity_id", flat=True))
    return render(
        request,
        "core/student_activities.html",
        {"activities": activities, "completed_ids": completed_ids, "join_form": JoinSessionForm()},
    )


def _normalize_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Present the persisted builder schema in the template's display schema."""
    normalized: list[dict[str, Any]] = []
    for block in blocks:
        block_type = block.get("type", "intro")
        # Every display key is present because Django resolves filter fallback
        # arguments eagerly (even when the primary value is already present).
        display_block: dict[str, Any] = {
            "type": "intro",
            "block_type": "intro",
            "question": "",
            "heading": "",
            "body": "",
            "text": "",
            "choices": [],
            "answer": None,
            "media_url": "",
            "alt_text": "",
        }
        if block_type == "question":
            display_block.update(
                {
                    "type": "question",
                    "block_type": "question",
                    "question": block.get("prompt", ""),
                    "heading": block.get("title", ""),
                    "body": block.get("explanation", ""),
                    "choices": block.get("options", []),
                    "answer": block.get("answer"),
                }
            )
        elif block_type in {"image", "video"}:
            display_block.update(
                {
                    "type": "image",
                    "block_type": "image",
                    "heading": block.get("title", ""),
                    "body": block.get("caption", ""),
                    "media_url": block.get("url", ""),
                    "alt_text": block.get("alt", block.get("title", "")),
                }
            )
        elif block_type == "resource":
            display_block.update(
                {
                    "heading": block.get("title", "Useful resource"),
                    "body": block.get("description", block.get("url", "")),
                    "text": block.get("description", block.get("url", "")),
                }
            )
        else:
            display_block.update(
                {
                    "heading": block.get("title", ""),
                    "body": block.get("body", ""),
                    "text": block.get("body", ""),
                }
            )
        normalized.append(display_block)
    return normalized


def _player_context(activity: Activity, session: ClassSession | None = None) -> dict[str, Any]:
    return {
        "activity": activity,
        "session": session,
        "blocks": _normalize_blocks(activity.content_json),
        "question_count": activity.question_count,
    }


@student_required
@require_GET
def student_activity_play(request: HttpRequest, activity_id: int) -> HttpResponse:
    activity = get_object_or_404(Activity.objects.select_related("author"), pk=activity_id, is_public=True)
    return render(request, "core/activity_player.html", _player_context(activity))


@student_required
@require_GET
def student_session(request: HttpRequest, session_id) -> HttpResponse:
    session = get_object_or_404(
        ClassSession.objects.select_related("activity", "teacher"),
        pk=session_id,
        is_active=True,
        enrollments__student=request.user,
    )
    return render(request, "core/activity_player.html", _player_context(session.activity, session))


@student_required
@require_POST
def student_join_session(request: HttpRequest) -> HttpResponse:
    form = JoinSessionForm(request.POST)
    if not form.is_valid():
        error = form.errors.get("join_code", ["Enter a valid code."])[0]
        return JsonResponse({"ok": False, "error": error}, status=400)
    session = ClassSession.objects.filter(join_code=form.cleaned_data["join_code"], is_active=True).first()
    if session is None:
        return JsonResponse({"ok": False, "error": "That live code is not active. Check with your teacher."}, status=404)
    SessionEnrollment.objects.get_or_create(session=session, student=request.user)
    return JsonResponse({"ok": True, "redirect_url": reverse("student_session", kwargs={"session_id": session.id})})


def _submitted_answers(request: HttpRequest) -> dict[str, Any]:
    """Read answers from either the JSON player request or a standard form POST."""
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        answers = payload.get("answers", {})
    else:
        raw = request.POST.get("answers", "{}")
        try:
            answers = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return answers if isinstance(answers, dict) else {}


@student_required
@require_POST
def student_complete_activity(request: HttpRequest, activity_id: int) -> HttpResponse:
    activity = get_object_or_404(Activity, pk=activity_id)
    session_id = request.POST.get("session_id")
    if request.content_type and "application/json" in request.content_type:
        try:
            session_id = json.loads(request.body.decode("utf-8")).get("session_id")
        except (UnicodeDecodeError, json.JSONDecodeError):
            session_id = None

    session = None
    if session_id:
        session = get_object_or_404(
            ClassSession,
            pk=session_id,
            activity=activity,
            is_active=True,
            enrollments__student=request.user,
        )
    elif not activity.is_public:
        return JsonResponse({"ok": False, "error": "This activity is available through a live session."}, status=403)

    answers = _submitted_answers(request)
    questions = [block for block in activity.content_json if block.get("type") == "question"]
    correct = 0
    recorded_answers: dict[str, int | None] = {}
    for index, block in enumerate(questions):
        answer = answers.get(str(index), answers.get(index))
        try:
            selected = int(answer)
        except (TypeError, ValueError):
            selected = None
        recorded_answers[str(index)] = selected
        if selected == block.get("answer"):
            correct += 1

    result, _ = StudentResult.objects.update_or_create(
        student=request.user,
        activity=activity,
        session=session,
        defaults={"score": correct, "total_questions": len(questions), "answers_json": recorded_answers},
    )
    payload = {
        "ok": True,
        "score": result.score,
        "total_questions": result.total_questions,
        "percentage": result.percentage,
        "redirect_url": reverse("student_results"),
    }
    if _is_json_request(request) or request.content_type and "application/json" in request.content_type:
        return JsonResponse(payload)
    messages.success(request, f"Activity complete — {result.score}/{result.total_questions} correct.")
    return redirect("student_results")


@student_required
@require_GET
def student_results(request: HttpRequest) -> HttpResponse:
    results = list(StudentResult.objects.filter(student=request.user).select_related("activity", "session"))
    return render(
        request,
        "core/results.html",
        {
            "results": results,
            "completed_count": len(results),
            "average_score": _average_percentage(results),
            "latest_result": results[0] if results else None,
        },
    )
