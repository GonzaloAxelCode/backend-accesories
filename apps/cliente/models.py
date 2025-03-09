from django.db import models

class Cliente(models.Model):
    number = models.CharField(max_length=8, unique=True,null=True, blank=True)  # Número de DNI
    full_name = models.CharField(max_length=255,null=True, blank=True)  # Nombre completo
    name = models.CharField(max_length=100,null=True, blank=True)  # Nombre(s)
    surname = models.CharField(max_length=100,null=True, blank=True)  # Apellido(s)
    verification_code = models.CharField(max_length=10, null=True, blank=True)  # Código de verificación (puede ser nulo)
    date_of_birth = models.DateField(null=True, blank=True)  # Fecha de nacimiento
    department = models.CharField(max_length=100,null=True, blank=True)  # Departamento
    province = models.CharField(max_length=100,null=True, blank=True)  # Provincia
    district = models.CharField(max_length=100,null=True, blank=True)  # Distrito
    address = models.TextField(null=True, blank=True)  # Dirección completa
    ubigeo = models.CharField(max_length=6,null=True, blank=True)  # Cóhigo de Ubigeo

    def __str__(self):
        return f"{self.full_name}"
