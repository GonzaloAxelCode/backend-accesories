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

    logo_img = models.ImageField(upload_to='tienda_logos/', null=True, blank=True)
    logo_img_dark = models.ImageField(upload_to='tienda_logos/', null=True, blank=True)
    banner_img = models.ImageField(upload_to='tienda_banners/', null=True, blank=True)
    certificado = models.FileField(upload_to='tienda_certificados/', null=True, blank=True)
    cert_clave_publica = models.TextField(null=True, blank=True)
    cert_clave_privada = models.TextField(null=True, blank=True)
    # Credenciales Clave SOL (SUNAT)
    sol_user = models.CharField(max_length=100, null=True, blank=True)
    sol_password = models.CharField(max_length=255, null=True, blank=True)
    design_boleta = models.CharField(max_length=100, default='', blank=True)
    design_factura = models.CharField(max_length=100, default='', blank=True)
    tipo_style_boleta_ticket = models.CharField(max_length=100, default='default', blank=True)
    tipo_style_boleta_pdf = models.CharField(max_length=100, default='default', blank=True)
    tipo_style_factura_pdf = models.CharField(max_length=100, default='default', blank=True)
    activo = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_deleted:
            self.activo = False
        if self.certificado:
            name = self.certificado.name.lower()
            if not name.endswith(('.p12', '.pfx', '.pem')):
                raise ValueError("El certificado debe ser un archivo .p12, .pfx o .pem")
        super().save(*args, **kwargs)

    propietario = models.ForeignKey(
        'user.UserAccount',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tiendas_propias'
    )

    tienda_padre = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sucursales'
    )

    date_created = models.DateTimeField(auto_now_add=True, null=True)
    correlativo_inicial_boleta = models.IntegerField(default=1,null=True, blank=True)
    correlativo_inicial_factura = models.IntegerField(default=1,null=True, blank=True)
    correlativo_inicial_nota_credito = models.IntegerField(default=1 ,null=True, blank=True)
    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

