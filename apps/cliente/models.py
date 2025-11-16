from django.db import models

from apps.tienda.models import Tienda

class Cliente(models.Model):
    document = models.CharField(max_length=8, unique=True,null=True, blank=True)  # Número de DNI
    fullname = models.CharField(max_length=255,null=True, blank=True)  # Nombre completo
    firstname = models.CharField(max_length=100,null=True, blank=True)  # Nombre(s)
    lastname = models.CharField(max_length=100,null=True, blank=True)  # Apellido(s)
    
    
    department = models.CharField(max_length=100,null=True, blank=True)  # Departamento
    province = models.CharField(max_length=100,null=True, blank=True)  # Provincia
    district = models.CharField(max_length=100,null=True, blank=True)  # Distrito
    address = models.TextField(null=True, blank=True)  # Dirección completa
    phone = models.CharField(max_length=15,null=True, blank=True)  # Número de teléfono
    email = models.EmailField(null=True, blank=True)  # Correo electrónico
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE,default=1) # type: ignore
    def __str__(self):
        return f"{self.fullname}"
