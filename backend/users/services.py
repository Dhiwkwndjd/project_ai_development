"""Вспомогательные функции приложения users."""

from django.db import DatabaseError

from users.models import ActivityLog


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(
    request,
    user,
    action,
    description="",
    entity=None,
    entity_type="",
    entity_id=None,
):
    """Записать действие в журнал. Ошибки журнала не должны ломать запрос.

    Для удалённых объектов `entity` уже нет, поэтому тип и ID можно
    передать явно.
    """
    if entity is not None:
        entity_type = entity.__class__.__name__.lower()
        entity_id = entity.pk

    try:
        return ActivityLog.objects.create(
            user=user if getattr(user, "pk", None) else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description[:255],
            ip_address=get_client_ip(request),
        )
    except DatabaseError:
        # Журнал не должен мешать основной операции.
        return None
