from django.db import models

from core import settings

# Create your models here.
from django.utils import timezone
class Tienda(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.TextField(null=True, blank=True)
    ciudad = models.CharField(max_length=100, null=True, blank=True)
    telefono = models.CharField(max_length=15, null=True, blank=True)
    activo = models.BooleanField(default=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    encargado = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tienda_encargada"
    )
    is_deleted = models.BooleanField(default=False)
    capacidad = models.IntegerField( null=True, blank=True)
    ruc = models.CharField(max_length=15,null=True)
    imagen = models.ImageField(upload_to='tiendas/', null=True, blank=True)

    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

