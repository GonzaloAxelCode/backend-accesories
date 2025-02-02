
from django.conf import settings

from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
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
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)