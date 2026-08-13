"""Small, explicit role guards for portal views."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(role: str):
    """Require an authenticated user with one specific platform role."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role != role:
                raise PermissionDenied("This portal is not available for your role.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


teacher_required = role_required("TEACHER")
student_required = role_required("STUDENT")
