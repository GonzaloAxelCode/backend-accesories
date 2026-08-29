from django.contrib import admin
from .models import Pedido, PedidoProducto


class PedidoProductoInline(admin.TabularInline):
    model = PedidoProducto
    extra = 0
    readonly_fields = ('producto', 'cantidad', 'stock_disponible', 'valor_unitario', 'valor_venta', 'igv', 'precio_unitario', 'costo_original')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'nombre_cliente', 'tipo_pedido', 'canal_venta', 'estado', 'estado_pago', 'total', 'fecha_hora', 'date_created')
    list_filter = ('estado', 'tipo_pedido', 'canal_venta', 'estado_pago', 'prioridad', 'tienda')
    search_fields = ('numero_pedido', 'nombre_cliente', 'numero_documento_cliente', 'referencia_externa')
    readonly_fields = ('date_created', 'fecha_realizacion')
    inlines = [PedidoProductoInline]
    fieldsets = (
        ('Identificación', {
            'fields': ('numero_pedido', 'usuario', 'tienda')
        }),
        ('Tipo y Canal', {
            'fields': ('tipo_pedido', 'canal_venta', 'prioridad')
        }),
        ('Fechas', {
            'fields': ('fecha_hora', 'fecha_vencimiento', 'fecha_entrega_estimada', 'fecha_realizacion', 'fecha_cancelacion')
        }),
        ('Estado', {
            'fields': ('estado', 'activo')
        }),
        ('Montos', {
            'fields': ('metodo_pago', 'subtotal', 'gravado_total', 'igv_total', 'descuento_total', 'costo_envio', 'total')
        }),
        ('Estado de Pago', {
            'fields': ('estado_pago', 'monto_adelanto', 'metodo_pago_adelanto')
        }),
        ('Cliente', {
            'fields': ('tipo_documento_cliente', 'numero_documento_cliente', 'nombre_cliente', 'email_cliente', 'telefono_cliente')
        }),
        ('Dirección de Envío', {
            'fields': ('direccion_envio', 'referencia_ubicacion')
        }),
        ('Notas', {
            'fields': ('observaciones', 'notas_internas', 'motivo_cancelacion')
        }),
        ('Referencias', {
            'fields': ('referencia_externa', 'productos_json')
        }),
    )
