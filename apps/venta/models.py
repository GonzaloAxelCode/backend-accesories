from django.db import models

from apps.cliente.models import Cliente
from apps.producto.models import Producto
from apps.tienda.models import Tienda
from core import settings

# Create your models here.
class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True) 
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    fecha_venta = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=100)
    estado = models.CharField(max_length=100, default='Completada')
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    notas = models.TextField(blank=True, null=True)
    factura = models.CharField(max_length=100, blank=True, null=True)
    
class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    notas = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=100, default='Entregado')
    activo = models.BooleanField(default=True)

    