from django.contrib import admin
from .models import Repuesto


@admin.register(Repuesto)
class RepuestoAdmin(admin.ModelAdmin):
    list_display = ("id", "tienda", "nombre", "modelos_compatibles", "ubicacion", "activo", "is_deleted")
    list_filter = ("ubicacion", "activo", "is_deleted")
    search_fields = ("nombre", "modelos_compatibles")
