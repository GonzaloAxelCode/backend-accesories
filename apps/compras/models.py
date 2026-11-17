from django.db import models
from decimal import Decimal
from apps.proveedor.models import Proveedor
from apps.tienda.models import Tienda


class ComprobanteCompra(models.Model):
    """Registro mínimo de una compra.

    Todo el detalle del comprobante vive en el XML (R2). Aquí solo se guarda
    lo necesario para consultar su validez en SUNAT + el link al XML.
    """

    TIPO_COMPROBANTE_CHOICES = [
        ('01', 'Factura'),
        ('03', 'Boleta'),
        ('07', 'Nota de crédito'),
    ]

    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    # Snapshot del RUC emisor: la consulta SUNAT usa este valor aunque el
    # proveedor se edite o se borre después (SET_NULL).
    ruc_proveedor = models.CharField(max_length=11, null=True, blank=True)
    tipo_comprobante = models.CharField(max_length=2, choices=TIPO_COMPROBANTE_CHOICES)
    serie = models.CharField(max_length=10)
    correlativo = models.CharField(max_length=20)

    # Archivos en R2 (carpeta por comprobante).
    # Constancia de validación SUNAT (la genera el flujo guardar).
    xml_constancia = models.URLField(max_length=500, null=True, blank=True)
    # XML real del proveedor (lo adjunta el usuario, se valida que corresponda).
    xml_comprobante = models.URLField(max_length=500, null=True, blank=True)
    # PDF del proveedor.
    pdf_url = models.URLField(max_length=500, null=True, blank=True)

    # Monto total del comprobante (declarado por el usuario desde su PDF).
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    # Último estado SUNAT conocido ("0001" = existe y aceptado).
    estado_codigo = models.CharField(max_length=10, null=True, blank=True)
    estado_descripcion = models.CharField(max_length=255, null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.serie:
            self.serie = self.serie.strip().upper()
        if self.correlativo:
            self.correlativo = self.correlativo.strip()
        if self.ruc_proveedor:
            self.ruc_proveedor = self.ruc_proveedor.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_comprobante_display()} {self.serie}-{self.correlativo}"

    class Meta:
        ordering = ["-date_created"]
        constraints = [
            models.UniqueConstraint(
                fields=["tienda", "ruc_proveedor", "tipo_comprobante", "serie", "correlativo"],
                name="uq_compra_tienda_ruc_tipo_serie_corr",
            ),
        ]
