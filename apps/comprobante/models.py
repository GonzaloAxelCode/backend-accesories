from django.db import models
from apps.venta.models import Venta

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

    def __str__(self):
        return f"{self.tipo_comprobante} {self.serie}-{self.correlativo}"


class NotaCredito(models.Model):
    comprobante_original = models.OneToOneField(
        ComprobanteElectronico, on_delete=models.CASCADE, related_name='nota_credito'
    )
    serie = models.CharField(max_length=4)  # Ejemplo: NC01
    numero = models.CharField(max_length=8)  # Ejemplo: 00012345
    motivo = models.TextField()
    fecha_emision = models.DateTimeField(auto_now_add=True)
    xml_firmado = models.TextField(blank=True, null=True)
    cdr_respuesta = models.TextField(blank=True, null=True)
    estado_sunat = models.CharField(max_length=50, default='Pendiente')  # Pendiente, Aceptado, Rechazado
