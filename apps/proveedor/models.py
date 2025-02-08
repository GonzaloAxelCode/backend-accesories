from django.db import models

# Create your models here.
#
class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    telefono = models.CharField(max_length=15)
    email = models.EmailField(blank=True,null=True)
    contacto = models.CharField(max_length=100,blank=True,null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    tipo_producto = models.CharField(max_length=100)
    calificacion = models.IntegerField(default=0)


    def __str__(self):
        return self.nombre
