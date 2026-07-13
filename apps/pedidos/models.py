
from django.db import models
from apps.cliente.models import Cliente
from apps.producto.models import Producto
from apps.tienda.models import Tienda
from core import settings
from django.utils import timezone
User = settings.AUTH_USER_MODEL
from django.utils.timezone import now


class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('COTIZADO', 'Cotizado'),
        ('PENDIENTE', 'Pendiente'),
        ('REALIZADO', 'Realizado'),
        ('CANCELADO', 'Cancelado'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    fecha_hora = models.DateTimeField()
    fecha_realizacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    metodo_pago = models.CharField(max_length=100, null=True)
    estado = models.CharField(max_length=100, choices=ESTADO_CHOICES, default='COTIZADO')

    activo = models.BooleanField(default=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    gravado_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    igv_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    productos_json = models.JSONField(default=list, blank=True)
    descuento_total = models.DecimalField(default=0, blank=True, max_digits=10, decimal_places=2)

    # Datos del cliente
    tipo_documento_cliente = models.CharField(max_length=2, null=True)
    numero_documento_cliente = models.CharField(max_length=15, null=True)
    nombre_cliente = models.CharField(max_length=255, null=True)
    email_cliente = models.EmailField(max_length=255, null=True)
    telefono_cliente = models.EmailField(max_length=255, null=True)
    direccion_cliente = models.EmailField(max_length=255, null=True)

    # Extras
    numero_pedido = models.CharField(max_length=50, unique=True)
    observaciones = models.TextField(null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.numero_pedido} - {self.nombre_cliente}"

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
