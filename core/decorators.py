# decorators.py
from functools import wraps
from django.http import JsonResponse

def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'error': 'Autenticación requerida'}, 
                status=401
            )
        if not request.user.is_superuser:
            return JsonResponse(
                {'error': 'Se requieren privilegios de superusuario'},
                status=403
            )
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Uso:
@superuser_required
def my_admin_view(request):
    # Tu lógica de vista
    pass