from django.db import models

from core import settings

# Create your models here.
from django.utils import timezone



class Tienda(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    razon_social = models.CharField(max_length=150, null=True, blank=True)
    ruc = models.CharField(max_length=11, null=True, blank=True)

    serie = models.CharField(max_length=150, null=True, blank=True)
    representante = models.CharField(max_length=150, null=True, blank=True)

    direccion = models.TextField(null=True, blank=True)
    telefono = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    sol_user = models.CharField(max_length=50, null=True, blank=True)
    sol_password = models.TextField(null=True, blank=True)

    logo_img = models.ImageField(upload_to='tienda_logos/', null=True, blank=True)
    activo = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True, null=True)
    correlativo_inicial_boleta = models.IntegerField(default=1,null=True, blank=True)
    correlativo_inicial_factura = models.IntegerField(default=1,null=True, blank=True)
    correlativo_inicial_nota_credito = models.IntegerField(default=1 ,null=True, blank=True)
    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

