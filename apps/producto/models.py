from django.db import models
from apps.categoria.models import Categoria
from apps.proveedor.models import Proveedor

class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    categoria_nombre = models.CharField(max_length=100, blank=True, null=True)
    sku = models.CharField(max_length=50, unique=True, blank=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    caracteristicas = models.JSONField(default=dict) 
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    

    def save(self, *args, **kwargs):
        if not self.sku and self.categoria:
            siglas = self.categoria.siglas_nombre_categoria.upper()  # type: ignore # Obtiene las siglas
            ultimo_producto = Producto.objects.filter(categoria=self.categoria).order_by('-id').first()
            nuevo_numero = int(ultimo_producto.sku.split('-')[1]) + 1 if ultimo_producto else 1
            self.sku = f"{siglas}-{nuevo_numero:06d}" 
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
