from django.db import models
from django.db.models import Q
from apps.tienda.models import Tienda


class Celular(models.Model):
    MARCA_CHOICES = [
        ("Apple", "Apple"),
        ("Samsung", "Samsung"),
        ("Xiaomi", "Xiaomi"),
        ("Redmi", "Redmi"),
        ("Motorola", "Motorola"),
        ("Honor", "Honor"),
        ("Realme", "Realme"),
        ("Infinix", "Infinix"),
        ("Oppo", "Oppo"),
        ("Vivo", "Vivo"),
    ]
    COLOR_CHOICES = [
        ("Negro", "Negro"),
        ("Blanco", "Blanco"),
        ("Azul", "Azul"),
        ("Titanio", "Titanio"),
        ("Verde", "Verde"),
        ("Rosado", "Rosado"),
    ]
    MEMORIA_CHOICES = [
        ("128 GB", "128 GB"),
        ("256 GB", "256 GB"),
        ("512 GB", "512 GB"),
        ("1 TB", "1 TB"),
    ]
    RAM_CHOICES = [
        ("4 GB", "4 GB"),
        ("6 GB", "6 GB"),
        ("8 GB", "8 GB"),
        ("12 GB", "12 GB"),
        ("16 GB", "16 GB"),
    ]
    ESTADO_EQUIPO_CHOICES = [
        ("Sellado", "Sellado"),
        ("Nuevo", "Nuevo"),
        ("Seminuevo", "Seminuevo"),
        ("Reacondicionado", "Reacondicionado"),
    ]

    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name="celulares")
    marca = models.CharField(max_length=50, choices=MARCA_CHOICES)
    modelo = models.CharField(max_length=100)
    color = models.CharField(max_length=30, choices=COLOR_CHOICES)
    memoria = models.CharField(max_length=20, choices=MEMORIA_CHOICES)
    ram = models.CharField(max_length=20, choices=RAM_CHOICES, blank=True, null=True)

    estado_equipo = models.CharField(max_length=20, choices=ESTADO_EQUIPO_CHOICES, default="Nuevo")
    imei1 = models.CharField(max_length=20)
    imei2 = models.CharField(max_length=20, blank=True, null=True)
    dualSim = models.BooleanField(default=False)

    costo_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    disponible = models.BooleanField(default=True)

    imagen1 = models.ImageField(upload_to="celulares/", null=True, blank=True)
    imagen2 = models.ImageField(upload_to="celulares/", null=True, blank=True)

    activo = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Si se desactiva o elimina, no puede quedar disponible
        if not self.activo or self.is_deleted:
            self.disponible = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.imei1})"

    class Meta:
        ordering = ["-date_created"]
        constraints = [
            models.UniqueConstraint(
                fields=["tienda", "imei1"],
                condition=Q(activo=True, is_deleted=False),
                name="unique_celular_imei1_por_tienda",
            ),
        ]
