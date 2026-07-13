from django.db import models
from apps.tienda.models import Tienda


class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    ruc = models.CharField(max_length=50, blank=True, null=True)
    razon_social = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    tipo_producto = models.CharField(max_length=100, blank=True, null=True)
    calificacion = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='proveedores')
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.ruc})"

    class Meta:
        ordering = ["-date_created"]
        constraints = [
            models.UniqueConstraint(
                fields=['ruc', 'tienda'],
                condition=models.Q(activo=True),
                name='unique_ruc_activo_por_tienda'
            ),
            models.UniqueConstraint(
                fields=['nombre', 'tienda'],
                condition=models.Q(activo=True),
                name='unique_nombre_activo_por_tienda'
            ),
        ]

