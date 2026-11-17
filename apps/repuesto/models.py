from django.db import models
from django.db.models import Q
from apps.tienda.models import Tienda
from apps.categoria.models import Categoria
from apps.proveedor.models import Proveedor


class Repuesto(models.Model):
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name="repuestos")
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="repuestos")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="repuestos")
    nombre = models.CharField(max_length=200, default="")
    modelos_compatibles = models.CharField(max_length=200, blank=True, default="")
    ubicacion = models.CharField(max_length=100, blank=True, null=True)

    stock = models.IntegerField(default=0)
    valorizacion = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    imagen1 = models.ImageField(upload_to="repuestos/", null=True, blank=True)
    imagen2 = models.ImageField(upload_to="repuestos/", null=True, blank=True)

    activo = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre}"

    class Meta:
        ordering = ["-date_created"]
        constraints = [
            models.UniqueConstraint(
                fields=["tienda", "nombre"],
                condition=Q(activo=True, is_deleted=False),
                name="unique_repuesto_nombre_por_tienda",
            ),
        ]
