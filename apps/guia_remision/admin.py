from django.contrib import admin

from .models import (
    GuiaDocumentoRelacionado,
    GuiaRemision,
    GuiaRemisionConductor,
    GuiaRemisionItem,
)


class GuiaRemisionItemInline(admin.TabularInline):
    model = GuiaRemisionItem
    extra = 0


class GuiaDocumentoRelacionadoInline(admin.TabularInline):
    model = GuiaDocumentoRelacionado
    extra = 0


class GuiaRemisionConductorInline(admin.TabularInline):
    model = GuiaRemisionConductor
    extra = 0


@admin.register(GuiaRemision)
class GuiaRemisionAdmin(admin.ModelAdmin):
    list_display = ("serie", "correlativo", "tienda", "mod_traslado", "estado", "estado_sunat")
    list_filter = ("mod_traslado", "estado", "estado_sunat", "serie")
    search_fields = ("serie", "correlativo", "numero_guia", "dest_num_doc", "dest_nombre")
    inlines = [
        GuiaRemisionItemInline,
        GuiaDocumentoRelacionadoInline,
        GuiaRemisionConductorInline,
    ]
    readonly_fields = ("payload_enviado", "respuesta_sunat", "date_created", "date_updated")
