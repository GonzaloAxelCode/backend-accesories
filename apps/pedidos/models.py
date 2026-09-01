from django.db import models
from apps.producto.models import Producto
from apps.tienda.models import Tienda
from core import settings

User = settings.AUTH_USER_MODEL


class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('COTIZADO', 'Cotizado'),
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADO', 'Confirmado'),
        ('EN_PREPARACION', 'En preparación'),
        ('LISTO', 'Listo'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]

    TIPO_PEDIDO_CHOICES = [
        ('MESA', 'Mesa'),
        ('DELIVERY', 'Delivery'),
        ('TAKEAWAY', 'Takeaway'),
        ('MOSTRADOR', 'Mostrador'),
    ]

    CANAL_CHOICES = [
        ('PRESENCIAL', 'Presencial'),
        ('WHATSAPP', 'WhatsApp'),
        ('WEB', 'Web'),
        ('TELEFONO', 'Teléfono'),
        ('TIKTOK', 'TikTok'),
    ]

    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PARCIAL', 'Parcial'),
        ('PAGADO', 'Pagado'),
    ]

    PRIORIDAD_CHOICES = [
        ('NORMAL', 'Normal'),
        ('URGENTE', 'Urgente'),
    ]

    # Relaciones
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)

    # Identificación
    numero_pedido = models.CharField(max_length=50, unique=True)

    # Tipo y canal
    tipo_pedido = models.CharField(max_length=20, choices=TIPO_PEDIDO_CHOICES, default='MOSTRADOR')
    canal_venta = models.CharField(max_length=20, choices=CANAL_CHOICES, default='PRESENCIAL')

    # Fechas
    fecha_hora = models.DateTimeField()
    fecha_realizacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    fecha_entrega_estimada = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)

    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='COTIZADO')
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='NORMAL')
    activo = models.BooleanField(default=True)

    # Montos
    metodo_pago = models.CharField(max_length=100, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gravado_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    igv_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Estado de pago
    estado_pago = models.CharField(max_length=10, choices=ESTADO_PAGO_CHOICES, default='PENDIENTE')
    monto_adelanto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    metodo_pago_adelanto = models.CharField(max_length=100, null=True, blank=True)

    # Datos del cliente
    tipo_documento_cliente = models.CharField(max_length=2, null=True, blank=True)
    numero_documento_cliente = models.CharField(max_length=15, null=True, blank=True)
    nombre_cliente = models.CharField(max_length=255, null=True, blank=True)
    email_cliente = models.EmailField(max_length=255, null=True, blank=True)
    telefono_cliente = models.CharField(max_length=20, null=True, blank=True)

    # Dirección de envío
    direccion_envio = models.TextField(null=True, blank=True)
    referencia_ubicacion = models.CharField(max_length=255, null=True, blank=True)

    # Notas
    observaciones = models.TextField(null=True, blank=True)
    notas_internas = models.TextField(null=True, blank=True)
    motivo_cancelacion = models.TextField(null=True, blank=True)

    # Referencia externa
    referencia_externa = models.CharField(max_length=100, null=True, blank=True)

    # JSON de productos
    productos_json = models.JSONField(default=list, blank=True)
    productos_pedido_json = models.TextField(default="", blank=True)

    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.numero_pedido} - {self.nombre_cliente or 'Sin cliente'}"

    class Meta:
        ordering = ["-date_created"]


class PedidoProducto(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad = models.IntegerField()
    stock_disponible = models.BooleanField(default=True)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    valor_venta = models.DecimalField(max_digits=10, decimal_places=2)
    base_igv = models.DecimalField(max_digits=10, decimal_places=2)
    porcentaje_igv = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    igv = models.DecimalField(max_digits=10, decimal_places=2)
    tipo_afectacion_igv = models.CharField(max_length=10)
    total_impuestos = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    costo_original = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.producto} x{self.cantidad} (Pedido {self.pedido.numero_pedido})"

    class Meta:
        ordering = ["-date_created"]
