from rest_framework.views import exception_handler
from rest_framework.exceptions import PermissionDenied, NotAuthenticated
from apps.common.audit import record_audit_event


def security_exception_handler(exc, context):
    """
    Phase 7 Security Exception Handler:
    Catches permission denials and unauthenticated access violations across all DRF views,
    automatically writing an immutable append-only AuditEntry record.
    """
    response = exception_handler(exc, context)

    if isinstance(exc, (PermissionDenied, NotAuthenticated)):
        request = context.get('request')
        user = getattr(request, 'user', None)
        actor_username = user.username if user and user.is_authenticated else 'anonymous'
        actor_role = getattr(user, 'role', '') if user and user.is_authenticated else ''

        ip_address = None
        user_agent = ''
        path = ''
        method = ''
        if request:
            xf = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = xf.split(',')[0].strip() if xf else request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            path = request.path
            method = request.method

        view = context.get('view')
        view_name = view.__class__.__name__ if view else 'UnknownView'

        record_audit_event(
            action='PERMISSION_DENIED',
            entity_type='Endpoint',
            entity_id=f"{method} {path}".strip(),
            actor=user if user and user.is_authenticated else None,
            actor_username=actor_username,
            actor_role=actor_role,
            ip_address=ip_address,
            user_agent=user_agent,
            object_repr=f"Denied {method} {path} to {actor_username}",
            metadata={
                'view': view_name,
                'error_detail': str(exc),
                'status_code': response.status_code if response else 403,
            }
        )

    return response
