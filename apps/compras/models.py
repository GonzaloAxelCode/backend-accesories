from django.db import models
from django.core.validators import FileExtensionValidator
from apps.proveedor.models import Proveedor
from apps.tienda.models import Tienda


class ComprobanteCompra(models.Model):
    TIPO_COMPROBANTE_CHOICES = [
        ('01', 'Factura'),
        ('03', 'Boleta'),
    ]

    FORMA_PAGO_CHOICES = [
        ('CONTADO', 'Contado'),
        ('CREDITO', 'Crédito'),
    ]

    # --- Relaciones ---
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)

    # --- Identificación del comprobante ---
    tipo_comprobante = models.CharField(max_length=2, choices=TIPO_COMPROBANTE_CHOICES)
    serie = models.CharField(max_length=10)
    correlativo = models.CharField(max_length=20)

    # --- Fechas y condición de pago ---
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField(null=True, blank=True)
    forma_pago = models.CharField(
        max_length=10, choices=FORMA_PAGO_CHOICES, null=True, blank=True
    )

    # --- Montos ---
    moneda = models.CharField(max_length=10, default="PEN")
    gravadas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    op_exoneradas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    op_inafectas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    op_gratuitas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dctos_totales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    icbper = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igv = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # --- Datos del proveedor (emisor del comprobante) ---
    tipo_documento_proveedor = models.CharField(max_length=2, null=True, blank=True)
    numero_documento_proveedor = models.CharField(max_length=15, null=True, blank=True)
    nombre_proveedor = models.CharField(max_length=255, null=True, blank=True)

    # --- Trazabilidad / documentos vinculados ---
    documento_relacionado = models.CharField(max_length=30, null=True, blank=True)
    enlace_verificacion = models.URLField(max_length=300, null=True, blank=True)

    # --- Archivos ---
    archivo_xml = models.FileField(
        upload_to='compras/xml/',
        validators=[FileExtensionValidator(['xml'])],
        blank=True,
        null=True,
    )
    archivo_pdf = models.FileField(
        upload_to='compras/pdf/',
        validators=[FileExtensionValidator(['pdf'])],
        blank=True,
        null=True,
    )

    # --- Detalle (se mantiene como JSON, sin cambios) ---
    items = models.JSONField(default=list, blank=True)

    observaciones = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.get_tipo_comprobante_display()} {self.serie}-{self.correlativo}"

    class Meta:
        ordering = ["-date_created"]
        constraints = [
            models.UniqueConstraint(
                fields=["proveedor", "tipo_comprobante", "serie", "correlativo"],
                name="unique_comprobante_por_proveedor",
            )
        ]
