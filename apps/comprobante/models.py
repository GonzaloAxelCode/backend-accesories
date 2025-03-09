from django.db import models

from apps.venta.models import Venta


class ComprobanteElectronico(models.Model):
    TIPO_COMPROBANTE_CHOICES = [
        ('BOLETA', 'Boleta Electrónica'),
        ('FACTURA', 'Factura Electrónica'),
    ]
    
    venta = models.OneToOneField(
        Venta, on_delete=models.CASCADE, related_name='comprobante'
    )
    tipo_comprobante = models.CharField(max_length=10, choices=TIPO_COMPROBANTE_CHOICES)
    serie = models.CharField(max_length=4, null=True)  # Ejemplo: B001, F001
    numero = models.CharField(max_length=8, null=True, blank=True)  # Ejemplo: 00000001
    fecha_emision = models.DateTimeField(auto_now_add=True)
    
    # Datos del cliente
    tipo_documento_cliente = models.CharField(max_length=2, null=True)  # Ejemplo: 1 (DNI)
    numero_documento_cliente = models.CharField(max_length=15, null=True)
    nombre_cliente = models.CharField(max_length=255, null=True)
    direccion_cliente = models.CharField(max_length=255, null=True, blank=True)
    email_cliente = models.EmailField(null=True, blank=True)
    telefono_cliente = models.CharField(max_length=20, null=True, blank=True)
    
    # Totales
    gravadas = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    igv = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    valor_venta = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    # Otros
    leyenda = models.TextField(null=True, blank=True)
    xml_firmado = models.TextField(blank=True, null=True)  # Guarda el XML firmado
    codigo_hash = models.CharField(max_length=100, blank=True, null=True)
    cdr_respuesta = models.TextField(blank=True, null=True)  # Respuesta de SUNAT
    estado_sunat = models.CharField(max_length=50, default='Pendiente', null=True)  # Pendiente, Aceptado, Rechazado
    
    # URLs de documentos generados
    xml_url = models.URLField(max_length=500, null=True, blank=True)
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    cdr_url = models.URLField(max_length=500, null=True, blank=True)
    ticket_url = models.URLField(max_length=500, null=True, blank=True)
    
    def __str__(self):
        return f"{self.tipo_comprobante} {self.serie}-{self.numero}"

    def obtener_siguiente_correlativo(self):

        ultimo = ComprobanteElectronico.objects.filter(serie=self.serie).order_by('-numero').first()
        if ultimo and ultimo.numero.isdigit(): # type: ignore
            return str(int(ultimo.numero) + 1).zfill(8)  # type: ignore # Asegura 8 dígitos
        return "00000001"  # Si es el primer comprobante de la serie

    def save(self, *args, **kwargs):

        if not self.numero:
            self.numero = self.obtener_siguiente_correlativo()
        super().save(*args, **kwargs)


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
