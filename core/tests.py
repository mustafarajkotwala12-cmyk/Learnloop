import json

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Activity, ClassSession, SessionEnrollment, StudentResult, User


def quiz_blocks():
    return [
        {"type": "intro", "title": "Warm-up", "body": "Let's begin."},
        {
            "type": "question",
            "prompt": "Which number is even?",
            "options": ["3", "8", "11"],
            "answer": 1,
            "explanation": "8 is divisible by 2.",
        },
    ]


class ModelTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher@example.com", password="learnloop-pass", role=User.Role.TEACHER
        )

    def test_email_is_login_identifier(self):
        user = User.objects.create_user(email="student@example.com", password="learnloop-pass")
        self.assertEqual(user.username, None)
        self.assertEqual(user.role, User.Role.STUDENT)

    def test_activity_counts_questions_and_rejects_empty_content(self):
        activity = Activity.objects.create(title="Numbers", author=self.teacher, content_json=quiz_blocks())
        self.assertEqual(activity.question_count, 1)
        invalid = Activity(title="No blocks", author=self.teacher, content_json=[])
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_session_generates_six_character_code(self):
        activity = Activity.objects.create(title="Numbers", author=self.teacher, content_json=quiz_blocks())
        session = ClassSession.objects.create(activity=activity, teacher=self.teacher)
        self.assertRegex(session.join_code, r"^[A-Z0-9]{6}$")
        self.assertTrue(session.is_joinable)


class PortalFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher@example.com", password="learnloop-pass", role=User.Role.TEACHER
        )
        self.student = User.objects.create_user(email="student@example.com", password="learnloop-pass")
        self.activity = Activity.objects.create(
            title="Numbers and patterns",
            description="An introductory quiz.",
            author=self.teacher,
            is_public=True,
            content_json=quiz_blocks(),
        )

    def test_public_catalogue_searches_titles(self):
        response = self.client.get(reverse("browse"), {"q": "patterns"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.activity.title)
        response = self.client.get(reverse("browse"), {"q": "astronomy"})
        self.assertNotContains(response, self.activity.title)

    def test_login_redirects_by_role(self):
        response = self.client.post(
            reverse("login"), {"email": self.teacher.email, "password": "learnloop-pass"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_redirect"))
        response = self.client.get(reverse("portal_redirect"))
        self.assertRedirects(response, reverse("teacher_dashboard"))

    def test_registration_creates_a_role_aware_account(self):
        response = self.client.post(
            reverse("register"),
            {
                "first_name": "Nora",
                "last_name": "Mentor",
                "email": "nora@example.com",
                "role": User.Role.TEACHER,
                "password1": "A-strong-demo-password9",
                "password2": "A-strong-demo-password9",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_redirect"))
        self.assertEqual(User.objects.get(email="nora@example.com").role, User.Role.TEACHER)

    def test_student_cannot_open_teacher_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_build_activity_and_start_live_session(self):
        self.client.force_login(self.teacher)
        blocks = quiz_blocks()
        response = self.client.post(
            reverse("activity_create"),
            {
                "title": "New activity",
                "description": "Created through the builder.",
                "estimated_minutes": 12,
                "is_public": "on",
                "content_json": json.dumps(blocks),
            },
        )
        self.assertRedirects(response, reverse("teacher_dashboard"))
        created = Activity.objects.get(title="New activity")
        self.assertEqual(created.author, self.teacher)
        response = self.client.post(reverse("teacher_start_session", args=[created.id]))
        self.assertEqual(response.status_code, 302)
        session = ClassSession.objects.get(activity=created)
        self.assertEqual(response.url, reverse("teacher_session", args=[session.id]))

    def test_student_can_join_and_submit_a_live_quiz(self):
        session = ClassSession.objects.create(activity=self.activity, teacher=self.teacher)
        self.client.force_login(self.student)
        # A guessed UUID alone does not grant access to a live room.
        self.assertEqual(self.client.get(reverse("student_session", args=[session.id])).status_code, 404)
        response = self.client.post(reverse("student_join_session"), {"join_code": session.join_code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_url"], reverse("student_session", args=[session.id]))
        self.assertTrue(SessionEnrollment.objects.filter(session=session, student=self.student).exists())
        self.assertEqual(self.client.get(reverse("student_session", args=[session.id])).status_code, 200)

        response = self.client.post(
            reverse("student_complete_activity", args=[self.activity.id]),
            data=json.dumps({"session_id": str(session.id), "answers": {"0": 1}}),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["percentage"], 100)
        result = StudentResult.objects.get(student=self.student, activity=self.activity, session=session)
        self.assertEqual((result.score, result.total_questions), (1, 1))

    def test_closed_live_session_cannot_accept_late_submission(self):
        session = ClassSession.objects.create(activity=self.activity, teacher=self.teacher)
        self.client.force_login(self.student)
        self.client.post(reverse("student_join_session"), {"join_code": session.join_code})
        session.end()
        response = self.client.post(
            reverse("student_complete_activity", args=[self.activity.id]),
            {"session_id": str(session.id), "answers": json.dumps({"0": 1})},
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_live_code_has_actionable_json_error(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("student_join_session"), {"join_code": "ZZZZZZ"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["ok"])

    def test_all_primary_portal_pages_render(self):
        """Catch template/context drift across the role-specific experiences."""
        session = ClassSession.objects.create(activity=self.activity, teacher=self.teacher)

        self.client.force_login(self.teacher)
        for route in (
            reverse("teacher_dashboard"),
            reverse("activity_create"),
            reverse("teacher_session", args=[session.id]),
            reverse("teacher_evaluation"),
        ):
            self.assertEqual(self.client.get(route).status_code, 200, route)

        self.client.force_login(self.student)
        for route in (
            reverse("student_dashboard"),
            reverse("student_activities"),
            reverse("student_activity_play", args=[self.activity.id]),
            reverse("student_results"),
        ):
            self.assertEqual(self.client.get(route).status_code, 200, route)
