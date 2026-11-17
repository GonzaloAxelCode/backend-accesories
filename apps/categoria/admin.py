from django.contrib import admin

from .models import Categoria


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "tipo", "tienda", "activo", "update_enable")
    list_filter = ("tipo", "activo", "update_enable")
    search_fields = ("nombre",)
