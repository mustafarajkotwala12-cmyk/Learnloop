"""Create a small, safe local demo dataset.

The command is intentionally idempotent, so it is useful after a fresh local
migration without becoming a production deployment requirement.
"""

from django.core.management.base import BaseCommand

from core.models import Activity, ClassSession, StudentResult, User


class Command(BaseCommand):
    help = "Create demo teacher, student, activity, live session, and result."

    def handle(self, *args, **options):
        teacher, _ = User.objects.get_or_create(
            email="ada@learnloop.local",
            defaults={"first_name": "Ada", "last_name": "Teacher", "role": User.Role.TEACHER},
        )
        teacher.role = User.Role.TEACHER
        teacher.set_password("learnloop-demo")
        teacher.save()

        student, _ = User.objects.get_or_create(
            email="sam@learnloop.local",
            defaults={"first_name": "Sam", "last_name": "Student", "role": User.Role.STUDENT},
        )
        student.role = User.Role.STUDENT
        student.set_password("learnloop-demo")
        student.save()

        activity, _ = Activity.objects.get_or_create(
            title="The science of attention",
            author=teacher,
            defaults={
                "description": "A short interactive warm-up on focus, curiosity, and learning.",
                "is_public": True,
                "estimated_minutes": 8,
                "content_json": [
                    {
                        "type": "intro",
                        "title": "Ready to focus?",
                        "body": "Small choices can make a large difference to how we learn.",
                    },
                    {
                        "type": "question",
                        "prompt": "Which action is most likely to help you begin a difficult task?",
                        "options": [
                            "Wait for motivation", "Make the first step tiny", "Open more tabs", "Skip planning"],
                        "answer": 1,
                        "explanation": "A tiny first step lowers the friction to start.",
                    },
                    {
                        "type": "question",
                        "prompt": "What is a useful way to check understanding?",
                        "options": [
                            "Reread silently", "Explain it in your own words", "Avoid questions", "Memorize only headings"],
                        "answer": 1,
                        "explanation": "Retrieval and explanation reveal what you know.",
                    },
                ],
            },
        )
        session, _ = ClassSession.objects.get_or_create(activity=activity, teacher=teacher, is_active=True)
        StudentResult.objects.update_or_create(
            student=student,
            activity=activity,
            session=session,
            defaults={"score": 2, "total_questions": 2, "answers_json": {"0": 1, "1": 1}},
        )
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write("Teacher: ada@learnloop.local / learnloop-demo")
        self.stdout.write("Student: sam@learnloop.local / learnloop-demo")
        self.stdout.write(f"Live join code: {session.join_code}")
