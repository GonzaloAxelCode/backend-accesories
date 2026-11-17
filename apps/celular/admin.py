from django.contrib import admin
from .models import Celular


@admin.register(Celular)
class CelularAdmin(admin.ModelAdmin):
    list_display = ("id", "tienda", "marca", "modelo", "imei1", "disponible", "activo", "is_deleted")
    list_filter = ("marca", "estado_equipo", "disponible", "activo", "is_deleted")
    search_fields = ("modelo", "imei1", "imei2")
