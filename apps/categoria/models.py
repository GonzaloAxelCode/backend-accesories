from django.db import models

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
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE,default=1, related_name='categorias') # type: ignore
    color = models.CharField(max_length=50, blank=True)
    siglas_nombre_categoria = models.CharField(max_length=10, blank=True,null=True)
    def __str__(self):
        return self.nombre
