
from django.db import models


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
    activo = models.BooleanField(default=True)
    lote = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=100)
    # Nuevos campo
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.producto} en {self.tienda}"

