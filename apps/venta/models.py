from django.db import models
from apps.cliente.models import Cliente
from apps.producto.models import Producto
from apps.tienda.models import Tienda
from core import settings

User = settings.AUTH_USER_MODEL
from django.utils.timezone import now

class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    fecha_venta = models.DateTimeField(auto_now_add=True)
    fecha_realizacion = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=100)
    estado = models.CharField(max_length=100, default='Completada')
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    notas = models.TextField(blank=True, null=True)
    factura = models.CharField(max_length=100, blank=True, null=True)

    def cancelar_venta(self):
        """Método para cancelar la venta y registrar la fecha de cancelación."""
        if self.estado != "Cancelada":
            self.estado = "Cancelada"
            self.fecha_cancelacion = now()
            self.save()

class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    notas = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=100, default='Entregado')
    activo = models.BooleanField(default=True)
