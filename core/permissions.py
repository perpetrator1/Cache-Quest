from rest_framework import permissions
from django.db.models import Q


def check_last_admin(excluding_user):
    """
    Check if excluding this user would leave no active admins.
    
    Args:
        excluding_user: User instance to exclude from the check
        
    Returns:
        True if this is the last active admin, False otherwise
    """
    from core.models import User
    
    active_admins = User.objects.filter(
        role='admin',
        is_active=True
    ).exclude(id=excluding_user.id)
    
    return active_admins.count() == 0


class IsAdminRole(permissions.BasePermission):
    """
    Permission class that only allows users with role='admin'.
    """
    message = 'Admin privileges required.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'admin'
        )
