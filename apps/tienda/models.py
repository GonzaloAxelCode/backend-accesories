from django.db import models

from core import settings

# Create your models here.

class Tienda(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    ciudad = models.CharField(max_length=100, null=True, blank=True)
    telefono = models.CharField(max_length=15)
    activo = models.BooleanField(default=True, null=True)
    encargado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    capacidad = models.IntegerField( null=True, blank=True)
    ruc = models.CharField(max_length=15)
    imagen = models.ImageField(upload_to='tiendas/', null=True, blank=True)

    def __str__(self):
        return self.nombre
