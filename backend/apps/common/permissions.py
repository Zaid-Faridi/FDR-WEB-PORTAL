from rest_framework import permissions

class IsAdminUserRole(permissions.BasePermission):
    """Allows access only to Admin users or superusers."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            getattr(request.user, 'role', None) == 'ADMIN' or request.user.is_superuser
        ))


class IsScrutinyOfficer(permissions.BasePermission):
    """Allows access to Scrutiny Officers (and Admins/Superusers)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            getattr(request.user, 'role', None) in ['SCRUTINY_OFFICER', 'ADMIN'] or request.user.is_superuser
        ))


class IsApprovingAuthority(permissions.BasePermission):
    """Allows access to Approving Authorities (and Admins/Superusers)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            getattr(request.user, 'role', None) in ['APPROVING_AUTHORITY', 'ADMIN'] or request.user.is_superuser
        ))


class IsInstitutionUser(permissions.BasePermission):
    """Allows access to authenticated Institution users."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == 'INSTITUTION' and
            request.user.institution_id is not None
        )


class InstrumentAccessPermission(permissions.BasePermission):
    """
    Enforces role-based instrument data segregation and actions:
    - Institution users can ONLY access instruments belonging to their institution.
    - Cross-institution access is strictly denied (403/404).
    - Officers, Approving Authorities, and Admins can view all instruments.
    - Specific actions are restricted by role.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Superuser and Admin can access all
        if user.is_superuser or getattr(user, 'role', None) == 'ADMIN':
            return True

        # Scrutiny Officers and Approving Authorities can view all instruments nationwide
        if getattr(user, 'role', None) in ['SCRUTINY_OFFICER', 'APPROVING_AUTHORITY']:
            return True

        # Institution role: STRICT isolation
        if getattr(user, 'role', None) == 'INSTITUTION':
            if not user.institution_id:
                return False
            # Check ownership
            return obj.institution_id == user.institution_id

        return False
