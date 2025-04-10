# middleware.py
from django.http import JsonResponse


class AuthSuperuserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Solo aplicar a URLs que comiencen con /admin/
        if not request.path.startswith('/admin/'):
            return None
            
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Login requerido'}, status=401)
            
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Se requiere superusuario'}, status=403)