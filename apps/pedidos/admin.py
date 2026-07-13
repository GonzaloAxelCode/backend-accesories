from django.contrib import admin
from .models import Pedido, PedidoProducto


class PedidoProductoInline(admin.TabularInline):
    model = PedidoProducto
    extra = 0
    readonly_fields = ('producto', 'cantidad', 'stock_disponible', 'valor_unitario', 'valor_venta', 'igv', 'precio_unitario', 'costo_original')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'nombre_cliente', 'estado', 'total', 'fecha_hora', 'date_created')
    list_filter = ('estado', 'tienda')
    search_fields = ('numero_pedido', 'nombre_cliente', 'numero_documento_cliente')
    inlines = [PedidoProductoInline]
