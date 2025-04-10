# permissions.py
from rest_framework import permissions

class IsSuperUser(permissions.BasePermission):
    """
    Permiso que solo permite acceso a superusuarios
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser and request.user.is_authenticated 

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_superuser  and request.user.is_authenticated 