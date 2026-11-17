
from django.db import models
from django.utils import timezone
from apps.tienda.models import Tienda

# Create your models here.
#
class Categoria(models.Model):
    TIPO_CHOICES = [
        ("REPUESTO", "REPUESTO"),
        ("ACCESORIO", "ACCESORIO"),
    ]
    nombre = models.CharField(max_length=200, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="ACCESORIO")
    descripcion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='categorias/', null=True, blank=True)   
    orden = models.IntegerField(default=0, null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    destacado = models.BooleanField(default=False,null=True, blank=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='categorias',null=True, blank=True) # type: ignore
    color = models.CharField(max_length=50, blank=True,null=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    caracteristicas_template = models.JSONField(default=list, blank=True)
    update_enable = models.BooleanField(default=True, help_text="False = categoría predefinida del sistema, no editable. True = creada por el usuario, editable.")

    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)
        constraints = [
            models.UniqueConstraint(fields=["tienda", "nombre"], name="uq_categoria_tienda_nombre"),
        ]

