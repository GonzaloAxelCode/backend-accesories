from django.db import models
from apps.venta.models import Venta
from django.utils import timezone
class ComprobanteElectronico(models.Model):
    venta = models.OneToOneField(
        Venta, on_delete=models.CASCADE, related_name='comprobante'
    )
    tipo_comprobante = models.CharField(max_length=10)
    serie = models.CharField(max_length=4, null=True)  # Ejemplo: B001 o F001
    fecha_emision = models.DateTimeField(auto_now_add=True)
    correlativo = models.CharField(max_length=8, null=True)  # Ahora es de 8 dígitos
    moneda = models.CharField(max_length=10, null=True)
    gravadas = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    igv = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    valorVenta = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    leyenda = models.TextField(null=True, blank=True)
    
    # Datos del cliente
    tipo_documento_cliente = models.CharField(max_length=2, null=True)  # Ejemplo: 1 (DNI)
    numero_documento_cliente = models.CharField(max_length=15, null=True)
    nombre_cliente = models.CharField(max_length=255, null=True)   

    xml_firmado = models.TextField(blank=True, null=True)  # Guarda el XML firmado
    codigo_hash = models.CharField(max_length=100, blank=True, null=True)
    cdr_respuesta = models.TextField(blank=True, null=True)  # Respuesta de SUNAT
    estado_sunat = models.CharField(max_length=50, default='Pendiente', null=True)  # Pendiente, Aceptado, Rechazado
    
    # URLs de documentos generados
    xml_url = models.URLField(max_length=500, null=True, blank=True)
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    cdr_url = models.URLField(max_length=500, null=True, blank=True)
    ticket_url = models.URLField(max_length=500, null=True, blank=True)
    items = models.JSONField(default=list)

    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    def __str__(self):
        return f"{self.tipo_comprobante} {self.serie}-{self.correlativo}"
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)




from django.db import models
from decimal import Decimal


class NotaCreditoDB(models.Model):
    """
    Representa una Nota de Crédito electrónica emitida para anular o corregir una venta.
    Cada nota de crédito está asociada a una venta (boleta o factura).
    """

    venta = models.OneToOneField(
        Venta,
        on_delete=models.CASCADE,
        related_name="nota_credito",
        help_text="Venta original a la que se aplica la nota de crédito",
    )

    comprobante_modificado = models.ForeignKey(
       ComprobanteElectronico,
        on_delete=models.CASCADE,
        related_name="notas_credito",
        help_text="Comprobante electrónico original (factura o boleta) que se modifica",
    )

    serie = models.CharField(max_length=10)
    correlativo = models.CharField(max_length=8)

    tipo_comprobante_modifica = models.CharField(
        max_length=2,
        choices=[
            ("01", "Factura electrónica"),
            ("03", "Boleta de venta electrónica"),
        ],
        help_text="Tipo de comprobante que se modifica",
    )
    serie_modifica = models.CharField(max_length=10)
    correlativo_modifica = models.CharField(max_length=8)

    tipo_motivo = models.CharField(
        max_length=2,
        choices=[
            ("01", "Anulación de la operación"),
            ("02", "Anulación por error en el RUC"),
            ("03", "Corrección por error en la descripción"),
            ("04", "Descuento global"),
            ("05", "Descuento por ítem"),
            ("06", "Devolución total"),
            ("07", "Devolución por ítem"),
        ],
        help_text="Código de motivo según catálogo SUNAT",
    )
    motivo = models.CharField(max_length=255, help_text="Descripción del motivo")

    moneda = models.CharField(max_length=3, default="PEN")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    estado_sunat = models.CharField(
        max_length=20,
        default="Pendiente",
        choices=[
            ("Pendiente", "Pendiente"),
            ("Aceptado", "Aceptado"),
            ("Rechazado", "Rechazado"),
            ("Error", "Error"),
        ],
    )

    xml_url = models.URLField(blank=True, null=True)
    pdf_url = models.URLField(blank=True, null=True)
    cdr_url = models.URLField(blank=True, null=True)

    fecha_emision = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota de Crédito {self.serie}-{self.correlativo} ({self.estado_sunat})"

    class Meta:
        verbose_name = "Nota de Crédito"
        verbose_name_plural = "Notas de Crédito"
        ordering = ["-fecha_emision"]
