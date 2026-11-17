from django.contrib import admin
from apps.compras.models import ComprobanteCompra


@admin.register(ComprobanteCompra)
class ComprobanteCompraAdmin(admin.ModelAdmin):
    list_display = ("id", "tienda", "ruc_proveedor", "tipo_comprobante", "serie", "correlativo", "estado_codigo", "date_created")
    list_filter = ("tipo_comprobante",)
    search_fields = ("serie", "correlativo", "ruc_proveedor")
