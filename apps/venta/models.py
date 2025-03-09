
from django.db import models
from apps.cliente.models import Cliente
from apps.producto.models import Producto
from apps.tienda.models import Tienda
from core import settings

User = settings.AUTH_USER_MODEL
from django.utils.timezone import now

class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tienda = models.ForeignKey(Tienda, on_delete=models.SET_NULL, null=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    fecha_realizacion = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    metodo_pago = models.CharField(max_length=100,null=True)
    estado = models.CharField(max_length=100, default='Completada')
    
    # Datos adicionales para facturación electrónica
    tipo_comprobante = models.CharField(max_length=50, choices=[('BOLETA', 'Boleta'), ('FACTURA', 'Factura')],null=True)
    serie = models.CharField(max_length=10,null=True)
    numero = models.CharField(max_length=20,null=True)
    ruc_empresa = models.CharField(max_length=15,null=True)
    razon_social = models.CharField(max_length=255,null=True)
    direccion_empresa = models.CharField(max_length=255,null=True)
    documento_cliente = models.CharField(max_length=20, null=True, blank=True)
    condicion_venta = models.CharField(max_length=50, choices=[('CONTADO', 'Contado'), ('CREDITO', 'Crédito')],null=True)
    total_gravado = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    igv = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    qr_url = models.URLField(null=True, blank=True)
    url_consulta = models.URLField(null=True, blank=True)
    

class DetalleVenta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')  
    cantidad = models.IntegerField(null=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0) # type: ignore
    notas = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
