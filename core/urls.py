
from django.conf import settings

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.conf.urls.static import static
from django.urls import path, include


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path('health/', health),
    path('admin/', admin.site.urls),   
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.jwt")),
    path("api/",include("apps.cliente.urls")),
    path("api/",include("apps.proveedor.urls")),
    path("api/",include("apps.tienda.urls")),
    path("api/",include("apps.categoria.urls")),
    path("api/",include("apps.user.urls")),
    path("api/",include("apps.producto.urls")),
    path("api/",include("apps.inventario.urls")),
    path("api/",include("apps.celular.urls")),
    path("api/",include("apps.repuesto.urls")),
    path("api/",include("apps.venta.urls")),
    
    path("api/",include("apps.comprobante.urls")),
    path("api/",include("apps.pedidos.urls")),
    path("api/",include("apps.compras.urls")),
    path("api/",include("apps.guia_remision.urls")),
    path("api/",include("apps.reports.urls")),
    path("api/",include("apps.ganancias.urls")),
    path("api/whatsapp/", include("apps.whatsapp.urls")),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)