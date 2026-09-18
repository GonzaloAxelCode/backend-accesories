from django.db import models

from core import settings
# Create your models here.
from django.utils import timezone


class PlanSuscripcion(models.Model):
    PERIODO_CHOICES = [
        ("mensual", "Mensual"),
        ("anual", "Anual"),
    ]

    nombre_plan = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    lista_descripcion = models.JSONField(
        default=list, blank=True,
        help_text="Lista de características del plan (array de strings)",
    )

    limite_boletas = models.PositiveIntegerField(default=0)
    limite_facturas = models.PositiveIntegerField(default=0)
    limite_personal = models.PositiveIntegerField(default=0)

    precio_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_anual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    moneda = models.CharField(max_length=3, default="PEN")
    periodo_facturacion = models.CharField(
        max_length=10, choices=PERIODO_CHOICES, default="mensual"
    )

    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plan de suscripción"
        verbose_name_plural = "Planes de suscripción"
        ordering = ["precio_mensual"]

    def __str__(self):
        return self.nombre_plan


class UsoMensualTienda(models.Model):
    """
    Contador agregado de comprobantes emitidos por tienda y mes.
    Se llena solo, vía signal (ver signals.py).
    """
    tienda = models.ForeignKey(
        "Tienda",
        on_delete=models.CASCADE,
        related_name="uso_mensual",
    )
    mes = models.DateField()  # siempre día 1 del mes
    boletas_emitidas = models.PositiveIntegerField(default=0)
    facturas_emitidas = models.PositiveIntegerField(default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Uso mensual de tienda"
        verbose_name_plural = "Usos mensuales de tiendas"
        constraints = [
            models.UniqueConstraint(fields=["tienda", "mes"], name="uq_uso_tienda_mes")
        ]

    def __str__(self):
        return f"{self.tienda} - {self.mes:%Y-%m}"


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

    plan = models.ForeignKey(
        "PlanSuscripcion",
        on_delete=models.PROTECT,
        related_name="tiendas",
        null=True,
        blank=True,
    )

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