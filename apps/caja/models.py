from django.db import models
from apps.tienda.models import Tienda

from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
User = get_user_model()
from datetime import datetime, timedelta
class Caja(models.Model):
    ESTADO_CHOICES = (
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
        ('cancelada', 'Cancelada'),
    )
    
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='cajas')
    usuario_apertura = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cajas_abiertas')
    usuario_cierre = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cajas_cerradas')

    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    fecha_reinicio = models.DateTimeField(null=True, blank=True)
    

    saldo_inicial = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, # type: ignore
        validators=[MinValueValidator(0)]
    )
    ingresos = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, # type: ignore
        validators=[MinValueValidator(0)]
    )
    egresos = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, # type: ignore
        validators=[MinValueValidator(0)]
    )
    saldo_final = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )

    estado = models.CharField(
        max_length=10, 
        choices=ESTADO_CHOICES, 
        default='abierta'
    )
    observacion = models.TextField(blank=True, null=True)



class OperacionCaja(models.Model):
    TIPO_OPERACION_CHOICES = (
        ('ingreso', 'Ingreso'),
        ('gasto', 'Gasto'),
        ('prestamo', 'Préstamo'),
        ('venta', 'Venta'),
        
    )

    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name='operaciones')
    id_operacion = models.CharField(max_length=10, unique=True, verbose_name="ID Operación")
    tipo = models.CharField(max_length=20, choices=TIPO_OPERACION_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='operaciones_caja')
    
    monto = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.TextField(blank=True, null=True)
    def save(self, *args, **kwargs):
        if not self.id_operacion:
            last = OperacionCaja.objects.order_by('-id').first()
            next_id = last.id + 1 if last else 1 # type: ignore
            self.id_operacion = f'OP{next_id:06d}'  # ejemplo: OP000001, OP000002, etc.
        super().save(*args, **kwargs) 
