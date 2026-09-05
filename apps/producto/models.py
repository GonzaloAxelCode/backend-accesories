from django.db import models
from apps import tienda
from apps.categoria.models import Categoria
from apps.proveedor.models import Proveedor
from apps.tienda.models import Tienda
from django.utils import timezone

class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    '''categoria_nombre = models.CharField(max_length=100, blank=True, null=True)'''
    sku = models.CharField(max_length=50, blank=True)
    imagen = models.ImageField(upload_to='productos/', default=None, null=True, blank=True)

    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    caracteristicas = models.JSONField(default=dict) 
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE,default=1) # type: ignore
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)     
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.sku:
            self.sku = f"PROD-{self.id:06d}"
            super().save(update_fields=["sku"])
    

    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

