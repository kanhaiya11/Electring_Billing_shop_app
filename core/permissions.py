from rest_framework.permissions import BasePermission


class IsShopUser(BasePermission):
    message = "A valid shop user account is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, "shop"))
