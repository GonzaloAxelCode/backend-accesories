
from django.db import models

from django.utils import timezone

from apps.producto.models import Producto
from apps.proveedor.models import Proveedor
from apps.tienda.models import Tienda
from core import settings

User = settings.AUTH_USER_MODEL
class Inventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    stock_minimo = models.IntegerField()
    stock_maximo = models.IntegerField()
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    activo = models.BooleanField(default=True)
    lote = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    costo_compra = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    costo_venta = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    costo_docena = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=100)
    # Nuevos campo
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.producto} en {self.tienda}"
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

