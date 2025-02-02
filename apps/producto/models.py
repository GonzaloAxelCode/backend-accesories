from django.db import models

from apps.categoria.models import Categoria
from apps.proveedor.models import Proveedor

# Create your models here.
class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    sku = models.CharField(max_length=50, unique=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    caracteristicas = models.JSONField(default=dict) 
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre
