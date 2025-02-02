from django.db import models

from apps.producto.models import Producto
from apps.proveedor.models import Proveedor
from apps.tienda.models import Tienda



# Create your models here.
#
class Inventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    stock_minimo = models.IntegerField()
    stock_maximo = models.IntegerField()
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    lote = models.CharField(max_length=100)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    
    estado = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.producto} en {self.tienda}"

