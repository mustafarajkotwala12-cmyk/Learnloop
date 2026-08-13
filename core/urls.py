from django.urls import path

from . import views


urlpatterns = [
    path("", views.landing, name="landing"),
    path("browse/", views.browse, name="browse"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("portal/", views.portal_redirect, name="portal_redirect"),
    path("teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/create/", views.activity_create, name="activity_create"),
    path("teacher/activity/<int:activity_id>/edit/", views.activity_edit, name="activity_edit"),
    path("teacher/activity/<int:activity_id>/start/", views.teacher_start_session, name="teacher_start_session"),
    path("teacher/session/<uuid:session_id>/", views.teacher_session, name="teacher_session"),
    path("teacher/eval/", views.teacher_evaluation, name="teacher_evaluation"),
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("student/activities/", views.student_activities, name="student_activities"),
    path("student/activity/<int:activity_id>/", views.student_activity_play, name="student_activity_play"),
    path("student/session/<uuid:session_id>/", views.student_session, name="student_session"),
    path("student/join/", views.student_join_session, name="student_join_session"),
    path("student/activity/<int:activity_id>/complete/", views.student_complete_activity, name="student_complete_activity"),
    path("student/results/", views.student_results, name="student_results"),
]
