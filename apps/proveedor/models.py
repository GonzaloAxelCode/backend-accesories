from django.db import models

from apps import tienda
from apps.tienda.models import Tienda
from django.utils import timezone
# Create your models here.
#
class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    telefono = models.CharField(max_length=15)
    email = models.EmailField(blank=True,null=True)
    contacto = models.CharField(max_length=100,blank=True,null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    tipo_producto = models.CharField(max_length=100)
    calificacion = models.IntegerField(default=0)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE,default=1, related_name='proveedores') # type: ignore
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

