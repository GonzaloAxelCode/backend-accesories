
from django.db import models
from apps.cliente.models import Cliente
from apps.producto.models import Producto
from apps.tienda.models import Tienda
from core import settings
from django.utils import timezone
User = settings.AUTH_USER_MODEL
from django.utils.timezone import now

class Venta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    fecha_hora = models.DateTimeField()
    fecha_realizacion = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    metodo_pago = models.CharField(max_length=100,null=True)
    estado = models.CharField(max_length=100, default='Completada')
   
    activo = models.BooleanField(default=True)
    tipo_comprobante = models.CharField(max_length=50, choices=[('BOLETA', 'Boleta'), ('FACTURA', 'Factura')],null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True) # type: ignore
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True) # type: ignore
    gravado_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True) # type: ignore
    igv_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True) # type: ignore
    productos_json = models.JSONField(default=list, blank=True)  # Compatible con PostgreSQL y SQLite en Django 3.1+
       # Datos del cliente
    tipo_documento_cliente = models.CharField(max_length=2, null=True)  # Ejemplo: 1 (DNI)
    numero_documento_cliente = models.CharField(max_length=15, null=True)
    nombre_cliente = models.CharField(max_length=255, null=True)   
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)

class VentaProducto(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE)  # Relación con la venta
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)  # Si el producto se elimina, queda nulo
    cantidad = models.IntegerField()
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)  # Precio sin IGV
    valor_venta = models.DecimalField(max_digits=10, decimal_places=2)  # Total sin IGV
    base_igv = models.DecimalField(max_digits=10, decimal_places=2)  # Base imponible
    porcentaje_igv = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)  # type: ignore # 18%
    igv = models.DecimalField(max_digits=10, decimal_places=2)  # Monto del IGV
    tipo_afectacion_igv = models.CharField(max_length=10)  # Código de afectación (Ej: "10" para gravado)
    total_impuestos = models.DecimalField(max_digits=10, decimal_places=2)  # Total de impuestos
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)  # Precio final (con IGV)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    class Meta:
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)
