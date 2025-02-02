from django.db import models

# Create your models here.
#
class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=100,unique=True,blank=True,null=True)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=15)
    direccion = models.TextField()
    pais = models.CharField(max_length=100)
    codigo_postal = models.CharField(max_length=10)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    genero = models.CharField(max_length=1, choices=[('M', 'Masculino'), ('F', 'Femenino')])
    activo = models.BooleanField(default=True)


    def __str__(self):
        return f"{self.nombre} {self.apellido}"
