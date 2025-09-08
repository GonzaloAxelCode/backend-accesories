
from django.db import models
from django.utils import timezone
from apps.tienda.models import Tienda

# Create your models here.
#
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='categorias/', null=True, blank=True)
    slug = models.SlugField(unique=True)
    orden = models.IntegerField(default=0)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    destacado = models.BooleanField(default=False)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='categorias',null=True, blank=True) # type: ignore
    color = models.CharField(max_length=50, blank=True)
    siglas_nombre_categoria = models.CharField(max_length=10, blank=True,null=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

