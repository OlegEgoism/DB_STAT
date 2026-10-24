from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

from db_statistics.models import DBUser


def register_failed_login(user):
    """Учитывает неудачную попытку входа и при необходимости блокирует пользователя.

    Единственное место, где считаются попытки: и view входа, и backend (Django
    admin) вызывают эту функцию, поэтому пороги и срок блокировки не могут
    разойтись. Возвращает (номер попытки, момент окончания блокировки или None).
    """
    user.failed_login_attempts += 1
    attempt_number = user.failed_login_attempts
    lockout_until = None
    if attempt_number >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
        user.failed_login_attempts = 0
        user.lockout_until = timezone.now() + timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS)
        lockout_until = user.lockout_until
    user.save(update_fields=["failed_login_attempts", "lockout_until"])
    return attempt_number, lockout_until


def clear_login_failures(user):
    """Сбрасывает счётчик неудачных попыток и блокировку после успешного входа."""
    if user.failed_login_attempts or user.lockout_until:
        user.failed_login_attempts = 0
        user.lockout_until = None
        user.save(update_fields=["failed_login_attempts", "lockout_until"])


class LockoutAwareModelBackend(ModelBackend):
    """Обычная аутентификация Django с той же блокировкой, что и в views.additional.login.

    Без этого Django admin (`/admin/login/`) обходил бы блокировку по неудачным
    попыткам входа стороной: она реализована только в собственном login()
    приложения, а не на уровне authenticate(), которым пользуется admin.
    Состояние (failed_login_attempts/lockout_until) общее с обычным входом —
    заблокированный пользователь не может войти ни туда, ни туда.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(DBUser.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = DBUser._default_manager.get_by_natural_key(username)
        except DBUser.DoesNotExist:
            # Матчит время выполнения с "пользователь найден", как и обычный ModelBackend.
            DBUser().set_password(password)
            return None

        if user.lockout_until and user.lockout_until > timezone.now():
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            clear_login_failures(user)
            return user

        register_failed_login(user)
        return None
