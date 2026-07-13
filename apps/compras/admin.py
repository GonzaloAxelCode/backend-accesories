from django.contrib import admin
from .models import ComprobanteCompra


@admin.register(ComprobanteCompra)
class ComprobanteCompraAdmin(admin.ModelAdmin):
    list_display = [
        'tipo_comprobante', 'serie', 'correlativo', 'proveedor',
        'fecha_emision', 'total', 'moneda', 'date_created',
    ]
    list_filter = ['tipo_comprobante', 'moneda', 'fecha_emision']
    search_fields = ['serie', 'correlativo', 'nombre_proveedor', 'numero_documento_proveedor']
    readonly_fields = ['date_created']
