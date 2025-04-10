from django.db import models

# Create your models here.
from django.db import models
from django.core.validators import FileExtensionValidator

from apps.proveedor.models import Proveedor

class Compra(models.Model):
    TIPO_COMPROBANTE_CHOICES = [
        ('01', 'Factura'),
        ('03', 'Boleta'),
        ('04', 'Nota de Crédito'),
    ]

    # Campos básicos
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)
    tipo_comprobante = models.CharField(max_length=2, choices=TIPO_COMPROBANTE_CHOICES)
    serie = models.CharField(max_length=10)
    numero = models.CharField(max_length=20)
    fecha = models.DateField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    igv = models.DecimalField(max_digits=10, decimal_places=2)

    # Relación con archivos (PDF/XML y TXT)
    def archivo_upload_path(instance, filename): # type: ignore
        return f'compras/{instance.fecha.year}/{instance.proveedor.ruc}/{filename}' # type: ignore

    archivo_pdf = models.FileField(
        upload_to=archivo_upload_path,
        validators=[FileExtensionValidator(['pdf'])],
        blank=True,
        null=True
    )
    archivo_xml = models.FileField(
        upload_to=archivo_upload_path,
        validators=[FileExtensionValidator(['xml'])],
        blank=True,
        null=True
    )
    archivo_txt = models.FileField(
        upload_to='compras/txt/',
        validators=[FileExtensionValidator(['txt'])],
        blank=True,
        null=True
    )

