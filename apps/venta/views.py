from collections import Counter
from datetime import timedelta
from django.utils.dateparse import parse_date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
from django.utils import timezone
import requests
import json
from datetime import datetime


from decimal import Decimal
from datetime import datetime, timedelta
from rest_framework.pagination import PageNumberPagination
from math import ceil
from time import localtime
from django.shortcuts import get_object_or_404
from django.db import transaction
import requests
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.conf import settings  
from django.utils import timezone
import json
from num2words import num2words  
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from django.db.models import Sum
from apps.comprobante.models import ComprobanteElectronico
from apps.inventario.models import Inventario
from apps.producto.serializers import ProductoSerializer
from apps.venta.serialzers import VentaSerializer
from core.settings import SUNAT_PHP
from .models import Venta, VentaProducto, Tienda, Producto
from apps.venta.utils import normalize_date


from django.contrib.auth import get_user_model
User = get_user_model()
from django.db.models import Max
from datetime import date, timedelta
from django.utils import timezone
from django.utils.timezone import localtime, make_aware
from django.db.models.functions import Coalesce

class VentaPagination(PageNumberPagination):
    page_size = 5  # Número predeterminado de ventas por página
    page_size_query_param = 'page_size'  
    max_page_size = 100  
    
    
class RegistrarVentaView(APIView):  
    def post(self, request):
        try:
            data = request.data

            # Validar que los datos obligatorios existan
            if not all(k in data for k in ["usuarioId", "metodoPago", "tipoComprobante", "productos"]):
                return Response({"error": "Faltan datos obligatorios"}, status=status.HTTP_400_BAD_REQUEST)
            def obtener_siguiente_serie_y_correlativo(tipo_comprobante):
                """
                Busca en la base de datos la última serie y correlativo según el tipo de comprobante.
                Si no hay comprobantes previos, inicia con 'F001' para facturas y 'B001' para boletas.
                """
                if tipo_comprobante.lower() == "factura":
                    serie_base = "F001"
                else:
                    serie_base = "B001"

                # Buscar el último comprobante con esa serie
                ultimo_comprobante = ComprobanteElectronico.objects.filter(serie__startswith=serie_base).order_by('-serie', '-correlativo').first()

                if ultimo_comprobante:
                    serie_actual = ultimo_comprobante.serie
                    correlativo_actual = int(ultimo_comprobante.correlativo) # type: ignore

                    # Si el correlativo llega a 99999999, pasamos a la siguiente serie (F002, B002, etc.)
                    if correlativo_actual >= 99999999:
                        nueva_serie = f"{serie_base[0]}{str(int(serie_actual[1:]) + 1).zfill(3)}" # type: ignore
                        nuevo_correlativo = "00000001"
                    else:
                        nueva_serie = serie_actual
                        nuevo_correlativo = str(correlativo_actual + 1).zfill(8)

                else:
                    # Si no hay comprobantes previos, iniciamos desde cero
                    nueva_serie = serie_base
                    nuevo_correlativo = "00000001"

                return nueva_serie, nuevo_correlativo

            # Buscar la tienda y el usuario por ID
            tienda = request.user.tienda
            

            usuario = request.user
            cliente_data = data["cliente"]
            
            fecha_hora_naive = datetime.now()  # Esto es naive

# Convertir a datetime aware
            fecha_hora_aware = timezone.make_aware(fecha_hora_naive)
            print(fecha_hora_aware) 


            with transaction.atomic():
                # Crear la venta
                venta = Venta.objects.create(
                    usuario=usuario,
                    tienda=tienda,
                    metodo_pago=data["metodoPago"],
                    tipo_comprobante=data["tipoComprobante"],
                    fecha_hora=fecha_hora_aware,
                    
                         tipo_documento_cliente = "6" if data["tipoComprobante"] == "Factura" else "1",
                             numero_documento_cliente=cliente_data["ruc"]  if data["tipoComprobante"] == "Factura" else cliente_data["numero"],
                             nombre_cliente= cliente_data["nombre_o_razon_social"] if data["tipoComprobante"] == "Factura" else cliente_data["nombre_completo"]
                     
                )
                subtotal = Decimal(0)
                gravado_total = Decimal(0)
                igv_total = Decimal(0)
                total = Decimal(0)
                exonerado_total = Decimal(0)


                productos_registrados = []
                productos_items_for_sunat = []
                # Iterar sobre los productos y guardarlos en VentaProducto
                for item in data["productos"]:
                    inventario = get_object_or_404(Inventario, id=item["inventarioId"])
                    producto = inventario.producto  # Obtener el producto asociado
                    cantidad = int(item["cantidad_final"])

                    # Obtener el precio con IGV desde inventario
                    precio_unitario = Decimal(inventario.costo_venta)  # type: ignore # Precio de venta final con IGV
                    porcentaje_igv = Decimal("18.00")  # ✅ Define el porcentaje como Decimal

                    # Calcular el valor unitario sin IGV
                    valor_unitario = precio_unitario / (Decimal("1.00") + (porcentaje_igv / Decimal("100.00")))  

                    # Calcular valores finales
                    valor_venta = cantidad * valor_unitario
                    igv = valor_venta * (porcentaje_igv / Decimal("100.00"))
                    total_impuestos = igv
                    
                    # Crear y guardar VentaProducto en la BD
                    venta_producto = VentaProducto.objects.create(
                        venta=venta,
                        producto=producto,
                        cantidad=cantidad,
                        valor_unitario=valor_unitario,
                        valor_venta=valor_venta,
                        base_igv=valor_venta,
                        porcentaje_igv=porcentaje_igv,
                        igv=igv,
                        tipo_afectacion_igv="10",  # Código de afectación IGV estándar
                        total_impuestos=total_impuestos,
                        precio_unitario=precio_unitario, 
                        
                        
                    )
                    venta_producto.save()
                    inventario.cantidad -= cantidad
                    inventario.save()

                    # Calcular totales
                    subtotal += valor_venta
                    gravado_total += valor_venta
                    igv_total += igv
                    total += precio_unitario * cantidad  # Total con IGV incluido

                    productos_registrados.append({
                        "producto_id": producto.id,  # type: ignore
                        "producto_nombre": producto.nombre,
                        "cantidad": cantidad,
                        "valor_unitario": float(valor_unitario),  # Sin IGV
                        "valor_venta": float(valor_venta),
                        "igv": float(igv),
                        "precio_unitario": float(precio_unitario)  # Con IGV,
                        
                    })
                    productos_items_for_sunat.append({
                              "codigo": producto.sku,
                            "unidad": "NIU",
                            "descripcion": producto.nombre,
                            "cantidad": cantidad,
                            "valorUnitario": round(float(valor_unitario), 2),
                            "valorVenta": round(float(valor_venta), 2),
                            "baseIgv": round(float(valor_venta), 2),
                            "porcentajeIgv": 18,
                            "igv": round(float(valor_venta * (porcentaje_igv / 100)), 2),  # ✅ CORRECCIÓN
                            "tipoAfectacionIgv": "10",
                            "totalImpuestos": round(float(valor_venta * (porcentaje_igv / 100)), 2),  # ✅ CORRECCIÓN
                            "precioUnitario": round(float(precio_unitario), 2),
                    }) 
                    venta.subtotal = subtotal
                    venta.gravado_total = gravado_total
                    venta.igv_total = igv_total
                    venta.total = total
                    
                    venta.productos_json = productos_registrados

                
                
                # 🔹 **Generar la leyenda en letras**
                leyenda = f"SON {num2words(total, lang='es').upper()} CON 00/100 SOLES"
                    
                    # 🔹 **JSON para enviar a la API de PHP**
                serie_generada, correlativo_generado = obtener_siguiente_serie_y_correlativo(data["tipoComprobante"])

                comprobante_data = {
                        "serie": serie_generada,
                        "correlativo": correlativo_generado,
                        "moneda": "PEN",
                        "gravadas": float(gravado_total),
                        "exoneradas": float(exonerado_total),
                        "igv": float(igv_total),
                        "valorVenta": float(subtotal),
                        "subTotal": float(subtotal + igv_total),
                        "total": float(total),
                        "leyenda": leyenda,
                        "cliente": {
                            "tipoDoc": "6" if data["tipoComprobante"] == "Factura" else "1",
                             "numDoc": cliente_data["ruc"]  if data["tipoComprobante"] == "Factura" else cliente_data["numero"],
                             "nombre": cliente_data["nombre_o_razon_social"] if data["tipoComprobante"] == "Factura" else cliente_data["nombre_completo"]
                        },
                        "items":productos_items_for_sunat
                }

                # 🔹 **Enviar la solicitud a la API PHP**
                print(productos_items_for_sunat)
                php_backend_url_boleta = SUNAT_PHP + "/src/api/boleta-post.php"
                php_backend_url_factura = SUNAT_PHP + "/src/api/factura-post.php"
                
                
                headers = {"Content-Type": "application/json"}
                response = requests.post(php_backend_url_factura if data["tipoComprobante"] == "Factura" else php_backend_url_boleta , json=comprobante_data, headers=headers)           
                
                try:
                     response.json()
                except Exception:
                    raise Exception(f"La API PHP devolvió una respuesta no JSON: {response.text}")

                # 🔹 **Verificar respuesta**
                if response.status_code == 200:
                    response_json = response.json()
                    # guardar el comprobante 
                    new_comprobante = ComprobanteElectronico.objects.create(
                            venta=venta,
                            tipo_comprobante=data["tipoComprobante"],
                            serie=comprobante_data["serie"],
                            correlativo=comprobante_data["correlativo"],
                            moneda=comprobante_data["moneda"],
                            gravadas=Decimal(comprobante_data["gravadas"]),
                            igv=Decimal(comprobante_data["igv"]),
                            valorVenta=Decimal(comprobante_data["valorVenta"]),
                            sub_total=Decimal(comprobante_data["subTotal"]),
                            total=Decimal(comprobante_data["total"]),
                            leyenda=comprobante_data["leyenda"],
                            tipo_documento_cliente=comprobante_data["cliente"]["tipoDoc"],
                            numero_documento_cliente=comprobante_data["cliente"]["numDoc"],
                            nombre_cliente=comprobante_data["cliente"]["nombre"],
                            estado_sunat="Aceptado" if response_json["cdr_codigo"] == "0" else "Rechazado", # type: ignore
                            xml_url=response_json.get("xml_url"), # type: ignore
                            pdf_url=response_json.get("pdf_url"), # type: ignore
                            cdr_url=response_json.get("cdr_url"), # type: ignore
                            ticket_url=response_json.get("ticket_url"), # type: ignore
                            items=comprobante_data["items"]
                        )
                    new_comprobante.save()
                    venta.save()
                    # Estructura JSON con toda la venta y sus productos
                    comprobante_json = {
                        "tipo_comprobante": new_comprobante.tipo_comprobante,
                        "serie": new_comprobante.serie,
                        "correlativo": new_comprobante.correlativo,
                        "moneda": new_comprobante.moneda,
                        "gravadas": float(new_comprobante.gravadas), # type: ignore
                        "igv": float(new_comprobante.igv), # type: ignore
                        "valorVenta": float(new_comprobante.valorVenta), # type: ignore
                        "sub_total": float(new_comprobante.sub_total), # type: ignore
                        "total": float(new_comprobante.total), # type: ignore
                        "leyenda": new_comprobante.leyenda,
                        "tipo_documento_cliente": new_comprobante.tipo_documento_cliente,
                        "numero_documento_cliente": new_comprobante.numero_documento_cliente,
                        "nombre_cliente": new_comprobante.nombre_cliente,
                        "estado_sunat": new_comprobante.estado_sunat,
                        "xml_url": new_comprobante.xml_url,
                        "pdf_url": new_comprobante.pdf_url,
                        "cdr_url": new_comprobante.cdr_url,
                        "ticket_url": new_comprobante.ticket_url,
                        "items": new_comprobante.items
                    }
                    venta_json = {
                        "id": venta.id, # type: ignore
                        "usuario":  usuario.id, # type: ignore
                        "tienda": tienda.id, # type: ignore
                        "metodo_pago": venta.metodo_pago,
                        "tipo_comprobante": venta.tipo_comprobante,
                        "metodo_pago" :venta.metodo_pago,
                        "estado" :venta.estado,
                        "activo" :venta.activo,
                        "fecha_hora": venta.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                        "fecha_realizacion" :venta.fecha_realizacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_realizacion else None,
                        "subtotal": float(subtotal),
                        "gravado_total": float(gravado_total),
                        "igv_total": float(igv_total),
                        "total": float(total),
                        "productos_json": json.dumps(productos_registrados),
                        "productos": productos_registrados,
                        "comprobante_data":comprobante_data ,                
                        "comprobante": comprobante_json                 
                    }
                    
                    
                    return Response(venta_json, status=status.HTTP_201_CREATED)
                else:
                    return Response({"error": "Error al generar el comprobante", "detalle": response}, status=status.HTTP_400_BAD_REQUEST)
            

        
        except Exception as e:
            
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)





class RegistrarVentaSinComprobanteView(APIView):
    def post(self, request):
        try:
            data = request.data

            # Validar datos obligatorios
            if not all(k in data for k in ["metodoPago", "tipoComprobante", "productos"]):
                return Response({"error": "Faltan datos obligatorios"}, status=status.HTTP_400_BAD_REQUEST)

            tienda = request.user.tienda
           
            usuario =request.user
            cliente_data = data.get("cliente", {})

            # Fecha aware
            fecha_hora_aware = timezone.make_aware(datetime.now())

            with transaction.atomic():
                # Crear venta
                venta = Venta.objects.create(
                    usuario=usuario,
                    tienda=tienda,
                    metodo_pago=data["metodoPago"],
                    tipo_comprobante=data["tipoComprobante"],
                    fecha_hora=fecha_hora_aware,
                    estado="Pendiente",  
                    tipo_documento_cliente = "6" if data["tipoComprobante"] == "Factura" else "1",
                             numero_documento_cliente=cliente_data["ruc"]  if data["tipoComprobante"] == "Factura" else cliente_data["numero"],
                             nombre_cliente= cliente_data["nombre_o_razon_social"] if data["tipoComprobante"] == "Factura" else cliente_data["nombre_completo"]
                     
                )

                subtotal = Decimal(0)
                gravado_total = Decimal(0)
                igv_total = Decimal(0)
                total = Decimal(0)
                exonerado_total = Decimal(0)

                productos_registrados = []

                for item in data["productos"]:
                    inventario = get_object_or_404(Inventario, id=item["inventarioId"])
                    producto = inventario.producto
                    cantidad = int(item["cantidad_final"])

                    precio_unitario = Decimal(inventario.costo_venta)  # type: ignore # con IGV
                    porcentaje_igv = Decimal("18.00")
                    valor_unitario = precio_unitario / (Decimal("1.00") + (porcentaje_igv / Decimal("100.00")))
                    valor_venta = cantidad * valor_unitario
                    igv = valor_venta * (porcentaje_igv / Decimal("100.00"))
                    total_impuestos = igv

                    # Guardar venta producto
                    VentaProducto.objects.create(
                        venta=venta,
                        producto=producto,
                        cantidad=cantidad,
                        valor_unitario=valor_unitario,
                        valor_venta=valor_venta,
                        base_igv=valor_venta,
                        porcentaje_igv=porcentaje_igv,
                        igv=igv,
                        tipo_afectacion_igv="10",
                        total_impuestos=total_impuestos,
                        precio_unitario=precio_unitario
                     
                    )

                    inventario.cantidad -= cantidad
                    inventario.save()

                    subtotal += valor_venta
                    gravado_total += valor_venta
                    igv_total += igv
                    total += precio_unitario * cantidad

                    productos_registrados.append({
                        "producto_id": producto.id, # type: ignore
                        "producto_nombre": producto.nombre,
                        "cantidad": cantidad,
                        "valor_unitario": float(valor_unitario),
                        "valor_venta": float(valor_venta),
                        "igv": float(igv),
                        "precio_unitario": float(precio_unitario)
                    })
                venta.estado = "Pendiente"  # Cambiar estado a Registrada
                venta.subtotal = subtotal
                venta.gravado_total = gravado_total
                venta.igv_total = igv_total
                venta.total = total
                venta.productos_json = productos_registrados
                venta.save()

                venta_json = {
                    "id": venta.id, # type: ignore
                    "usuario": usuario.id, # type: ignore
                    "tienda": tienda.id, # type: ignore
                    "metodo_pago": venta.metodo_pago,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "fecha_hora": venta.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                    "fecha_realizacion": venta.fecha_realizacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_realizacion else None,
                    "subtotal": float(subtotal),
                    "gravado_total": float(gravado_total),
                    "igv_total": float(igv_total),
                    "total": float(total),
                    "productos_json": json.dumps(productos_registrados),
                    "productos": productos_registrados,
                    "comprobante_data":None ,                
                    "comprobante": None  
                }
                
                return Response(venta_json, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)







class CancelarVentaView(APIView):
    def patch(self, request, venta_id):
        # Obtener la venta o devolver 404 si no existe
        venta = get_object_or_404(Venta, id=venta_id)

        # Verificar si la venta ya está cancelada
        if venta.estado == "Cancelado":
            return Response(
                {"message": "La venta ya está cancelada."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Actualizar el estado y la fecha de cancelación
        venta.estado = "Cancelado"
        
        venta.fecha_cancelacion = timezone.now()  # Asigna la fecha actual

        venta.save()

        return Response(
            {"message": "Venta cancelada exitosamente."}, 
            status=status.HTTP_200_OK
        )
        
''' no usar eso solo en desarrollo'''
class EliminarVentaView(APIView):
    def delete(self, request, venta_id):
        # Obtener la venta o devolver 404 si no existe
        venta = get_object_or_404(Venta, id=venta_id)
        venta.delete()
         
        '''Venta.objects.all().delete() '''
        return Response(
            {"message": "Venta eliminada (esto deberia ser en desarollo si esta en produccion puede generar errores)."}, 
            status=status.HTTP_200_OK
        )
        
    
class VentasResumenView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        tienda_id = request.user.tienda
     
        # Obtener la fecha y hora actual en la zona horaria de Lima, Perú
        today = localtime(now()).date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        current_year = today.year
        
        # Filtrar ventas activas de la tienda
        ventas_activas = Venta.objects.filter(tienda_id=tienda_id, activo=True)
        
        # Ventas del día
        today_sales = ventas_activas.filter(fecha_hora__date=today).aggregate(total=Sum("total"))['total'] or 0
        
        # Ventas de la semana (considerando el año)
        this_week_sales = ventas_activas.filter(
            fecha_hora__date__gte=start_of_week,
            fecha_hora__year=current_year
        ).aggregate(total=Sum("total"))['total'] or 0
        
        # Ventas del mes (considerando el año)
        this_month_sales = ventas_activas.filter(
            fecha_hora__date__gte=start_of_month,
            fecha_hora__year=current_year
        ).aggregate(total=Sum("total"))['total'] or 0
        
        return Response({
            "todaySales": today_sales,
            "thisWeekSales": this_week_sales,
            "thisMonthSales": this_month_sales
        })
        




class VentaSalesByDateView(APIView):
    def post(self, request, *args, **kwargs):
        # Obtener los rangos de fechas desde el cuerpo de la solicitud
        from_date = request.data.get('from_date')  # Expected format: [2025, 0, 1] para enero
        to_date = request.data.get('to_date')  # Expected format: [2025, 3, 1] para abril
        tienda_id = request.user.tienda# tienda_id

        if not from_date or not to_date:
            return Response({"error": "Se debe proporcionar un rango de fechas válido"}, status=status.HTTP_400_BAD_REQUEST)

        # Convertir de [year, month, day] a objetos datetime (sin horas, minutos ni segundos)
        # Ajustar el mes, ya que el mes está en formato 0-11
        from_date_obj = make_aware(datetime(from_date[0], from_date[1] + 1, from_date[2]))  # Ajuste mes
        to_date_obj = make_aware(datetime(to_date[0], to_date[1] + 1, to_date[2]))  # Ajuste mes

        # Convertir las fechas a solo la parte de la fecha (sin horas)
        from_date_obj = from_date_obj.date()
        to_date_obj = to_date_obj.date()

        # Generar todos los días en el rango especificado usando timedelta
        date_range = []
        current_date = from_date_obj
        while current_date <= to_date_obj:
            date_range.append(current_date)  # Añadir solo la parte de la fecha (sin hora)
            current_date += timedelta(days=1)  # Avanzar al siguiente día

        # Filtrar las ventas en el rango de fechas
        ventas = Venta.objects.filter(tienda=tienda_id, fecha_hora__gte=from_date_obj, fecha_hora__lte=to_date_obj)

        # Agrupar las ventas por fecha y calcular el total de ventas por fecha
        daily_sales = (
            ventas
            .values('fecha_hora__date')  # Agrupar solo por fecha (sin horas, minutos ni segundos)
            .annotate(total_sales=Sum('total'))  # Sumar las ventas totales por cada fecha
            .order_by('fecha_hora__date')  # Ordenar por fecha
        )

        # Crear un diccionario de ventas por fecha
        sales_by_date = {sale['fecha_hora__date']: sale['total_sales'] or 0 for sale in daily_sales}

        # Preparar los datos para la respuesta, asegurándonos de que todos los días en el rango estén presentes
        sales_date_range = [
            # Asegurarse de que el mes esté en formato 0-11 (como en Python)
            [f"{date.year}, {date.month - 1}, {date.day}", float(sales_by_date.get(date, 0))]  # Si no hay ventas, asignamos 0
            for date in date_range
        ]

        # Devolver los resultados
        return Response({"salesDateRangePerDay": sales_date_range}, status=status.HTTP_200_OK)



class ProductosMasVendidosView(APIView):
    def post(self, request):
        fd = request.data.get('from_date')
        td = request.data.get('to_date')
        tienda = request.user.tienda

        # Normalizar fechas
        fd = normalize_date(fd, end_of_day=False)
        td = normalize_date(td, end_of_day=True)

        # 1️⃣ Filtramos ventas
        ventas = Venta.objects.filter(
            tienda=tienda,
          
            activo=True
        )

        # 2️⃣ Productos de esas ventas
        venta_productos = VentaProducto.objects.filter(venta__in=ventas)

        # 3️⃣ Agrupar por producto
        productos_data = []
        contador = Counter()

        for vp in venta_productos:
            if vp.producto:  # evitar productos nulos
                contador[vp.producto.nombre] += vp.cantidad

        # 4️⃣ Armar respuesta
        for nombre, cantidad in contador.items():
            productos_data.append({
                "nombre": nombre,
                "cantidad_total_vendida": cantidad
            })

        # Ordenamos por más vendidos primero
        productos_data = sorted(productos_data, key=lambda x: x["cantidad_total_vendida"], reverse=True)

        return Response({"results": productos_data})
    
class VentasPerDayOrMonth(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        tienda_id = request.user.tienda
        year = int(request.data.get("year", 0))
        month = int(request.data.get("month", 0))
        day = int(request.data.get("day", 0))
        tipo = request.data.get("tipo", "default")  # El tipo será pasado en el body del request

        if not tienda_id:
            return Response({"error": "Se requiere el ID de la tienda."}, status=400)



        ventas_activas = Venta.objects.filter(tienda_id=tienda_id, activo=True)

        today_sales = None
        this_month_sales = None

        try:
            # Si el tipo es 'day_month_year' se calcula las ventas de un día específico
            if tipo == "day_month_year" :
                selected_date = date(year, month, day)
                today_sales = ventas_activas.filter(
                    fecha_hora__date=selected_date
                ).aggregate(total=Sum("total"))['total'] or 0
                

            # Si el tipo es 'month_year' se calcula las ventas del mes
            elif tipo == "month_year" and year and month:
                start_of_month = date(year, month, 1)
                if month == 12:
                    end_of_month = date(year + 1, 1, 1)
                else:
                    end_of_month = date(year, month + 1, 1)

                this_month_sales = ventas_activas.filter(
                    fecha_hora__date__gte=start_of_month,
                    fecha_hora__date__lt=end_of_month
                ).aggregate(total=Sum("total"))['total'] or 0
                

            # Si no se pasó el tipo o año, se responde por defecto
            else:
                return Response({
                    "todaySales": None,
                    "thisMonthSales": None,
                    "tipo": "default"
                })

        except ValueError:
            return Response({"error": "Fecha inválida."}, status=400)

        return Response({
            "todaySales": today_sales,
            "thisMonthSales": this_month_sales,
            "tipo": tipo
        })
        

        
class VentaBusquedaView(APIView):
    def post(self, request):
        
            page_number = int(request.data.get('page', 1))
            page_size = int(request.data.get('page_size', 5))
            tienda_id = request.user.tienda
            query = request.data.get('query', {})
            ventas = Venta.objects.all()
            ventas = ventas.filter(tienda_id=tienda_id)

            # Filtro por fechas
            from_date = query.get('from_date')
            to_date = query.get('to_date')
            
               
            from_date_obj = datetime(
                        year=from_date[0],
                        month=from_date[1] + 1,  # Convertir a 1-based
                        day=from_date[2]
            )
            to_date_obj = datetime(
                        year=to_date[0],
                        month=to_date[1] + 1,    # Convertir a 1-based
                        day=to_date[2],
                        hour=23,
                        minute=59,
                        second=59
            )
            
            
            ventas = ventas.filter(fecha_hora__range=(from_date_obj, to_date_obj))
             
             
            
    
            metodo_pago = query.get('metodo_pago')
            tipo_comprobante = query.get('tipo_comprobante')
            
            
            nombre_cliente = query.get('nombre_cliente')
            numero_documento_cliente = query.get('numero_documento_cliente')
            numero_comprobante = query.get('numero_comprobante')
            estado_sunat = query.get('estado_sunat')
            
            
            if metodo_pago  is not "":
                print(metodo_pago)
                ventas = ventas.filter(metodo_pago__icontains=metodo_pago)
            if estado_sunat  is not "":
                ventas = ventas.filter(comprobante__estado_sunat__icontains=estado_sunat)
            if tipo_comprobante  is not "":
                ventas = ventas.filter(tipo_comprobante__icontains=tipo_comprobante) 
            if numero_documento_cliente  is not "":
                ventas = ventas.filter(comprobante__numero_documento_cliente__icontains=numero_documento_cliente)
            if numero_comprobante  is not "":
                ventas = ventas.filter(comprobante__correlativo=numero_comprobante)
            
            if nombre_cliente  is not "":
                ventas = ventas.filter(comprobante__nombre_cliente__icontains=nombre_cliente)
                
                
            total_ventas = ventas.count()
            paginator = VentaPagination()
            result_page = paginator.paginate_queryset(ventas, request)
            total_pages = ceil(total_ventas / page_size)           
            
            next_page = page_number + 1 if page_number < total_pages else None
            previous_page = page_number - 1 if page_number > 1 else None
            
            
            ventas_json = []
            for venta in result_page: # type: ignore
                comprobante_venta = ComprobanteElectronico.objects.filter(venta=venta).first()
                comprobante_json = None
                productos = VentaProducto.objects.filter(venta=venta)

                if comprobante_venta:
                    comprobante_json = {
                        "tipo_comprobante": comprobante_venta.tipo_comprobante,
                        "serie": comprobante_venta.serie,
                        "correlativo": comprobante_venta.correlativo,
                        "moneda": comprobante_venta.moneda,
                        "gravadas": float(comprobante_venta.gravadas) if comprobante_venta.gravadas else None,
                        "igv": float(comprobante_venta.igv) if comprobante_venta.igv else None,
                        "valorVenta": float(comprobante_venta.valorVenta) if comprobante_venta.valorVenta else None,
                        "sub_total": float(comprobante_venta.sub_total) if comprobante_venta.sub_total else None,
                        "total": float(comprobante_venta.total) if comprobante_venta.total else None,
                        "leyenda": comprobante_venta.leyenda,
                        "tipo_documento_cliente": comprobante_venta.tipo_documento_cliente,
                        "numero_documento_cliente": comprobante_venta.numero_documento_cliente,
                        "nombre_cliente": comprobante_venta.nombre_cliente,
                        "estado_sunat": comprobante_venta.estado_sunat,
                        "xml_url": comprobante_venta.xml_url,
                        "pdf_url": comprobante_venta.pdf_url,
                        "cdr_url": comprobante_venta.cdr_url,
                        "ticket_url": comprobante_venta.ticket_url,
                        "items": comprobante_venta.items
                    }

                productos_json = [
                    {
                        "id": producto.id, # type: ignore
                        "producto": producto.producto.id if producto.producto else None, # type: ignore
                        "producto_nombre": producto.producto.nombre if producto.producto else "Producto eliminado",
                        "cantidad": producto.cantidad,
                        "valor_unitario": float(producto.valor_unitario),
                        "valor_venta": float(producto.valor_venta),
                        "base_igv": float(producto.base_igv),
                        "porcentaje_igv": float(producto.porcentaje_igv),
                        "igv": float(producto.igv),
                        "tipo_afectacion_igv": producto.tipo_afectacion_igv,
                        "total_impuestos": float(producto.total_impuestos),
                        "precio_unitario": float(producto.precio_unitario)
                    }
                    for producto in productos
                ]
                nota_credito = getattr(venta, "nota_credito", None)
                nota_credito_json = None
                if nota_credito:
                    nota_credito_json = {
                        "id": nota_credito.id,
                        "serie": nota_credito.serie,
                        "correlativo": nota_credito.correlativo,
                        "tipo_comprobante_modifica": nota_credito.tipo_comprobante_modifica,
                        "serie_modifica": nota_credito.serie_modifica,
                        "correlativo_modifica": nota_credito.correlativo_modifica,
                        "tipo_motivo": nota_credito.tipo_motivo,
                        "motivo": nota_credito.motivo,
                        "moneda": nota_credito.moneda,
                        "total": float(nota_credito.total),
                        "estado_sunat": nota_credito.estado_sunat,
                        "xml_url": nota_credito.xml_url,
                        "pdf_url": nota_credito.pdf_url,
                        "cdr_url": nota_credito.cdr_url,
                        "fecha_emision": nota_credito.fecha_emision.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                ventas_json.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id,
                    "fecha_hora": venta.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                    "fecha_realizacion": venta.fecha_realizacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "productos": productos_json,
                    "total": venta.total,
                    "productos_json": json.dumps(venta.productos_json, indent=4),
                    "comprobante": comprobante_json,
                    "comprobante_nota_credito":nota_credito_json
                })
   
            
            
            
            
            return Response({
               "count": total_ventas,
                "next": next_page,
                "previous": previous_page,
                "index_page":page_number - 1,
                "length_pages": total_pages ,
                "results": ventas_json,
                "search_ventas_found": "ventas_found" if total_ventas > 0 else "ventas_not_found",
            })
        

    
class VentasPorTiendaView(APIView):
    def get(self, request):
        try:
            # Obtener parámetros de la URL
            page_size = int(request.query_params.get('page_size', 5))
            page_number = int(request.query_params.get('page', 1))
            tienda_id = request.user.tienda
            
            # Filtro por fecha (ahora espera strings en formato YYYY-MM-DD)
            from_date_str = request.query_params.get('from_date')
            to_date_str = request.query_params.get('to_date')
     
            from_date_obj = datetime.strptime(from_date_str, '%Y-%m-%d')
            to_date_obj = datetime.strptime(to_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            ventas = Venta.objects.all()
            ventas = ventas.filter(tienda_id=tienda_id,fecha_hora__range=(from_date_obj, to_date_obj))
            
            
            total_ventas = ventas.count()
        
            paginator = VentaPagination()
            
            paginated_ventas = paginator.paginate_queryset(ventas, request)
            
            total_pages = ceil(total_ventas / page_size)
            
            ventas_json = []
            for venta in paginated_ventas: # type: ignore
                comprobante_venta = ComprobanteElectronico.objects.filter(venta=venta).first()
                comprobante_json = None
                productos = VentaProducto.objects.filter(venta=venta)

                if comprobante_venta:
                    comprobante_json = {
                        "tipo_comprobante": comprobante_venta.tipo_comprobante,
                        "serie": comprobante_venta.serie,
                        "correlativo": comprobante_venta.correlativo,
                        "moneda": comprobante_venta.moneda,
                        "gravadas": float(comprobante_venta.gravadas) if comprobante_venta.gravadas else None,
                        "igv": float(comprobante_venta.igv) if comprobante_venta.igv else None,
                        "valorVenta": float(comprobante_venta.valorVenta) if comprobante_venta.valorVenta else None,
                        "sub_total": float(comprobante_venta.sub_total) if comprobante_venta.sub_total else None,
                        "total": float(comprobante_venta.total) if comprobante_venta.total else None,
                        "leyenda": comprobante_venta.leyenda,
                        "tipo_documento_cliente": comprobante_venta.tipo_documento_cliente,
                        "numero_documento_cliente": comprobante_venta.numero_documento_cliente,
                        "nombre_cliente": comprobante_venta.nombre_cliente,
                        "estado_sunat": comprobante_venta.estado_sunat,
                        "xml_url": comprobante_venta.xml_url,
                        "pdf_url": comprobante_venta.pdf_url,
                        "cdr_url": comprobante_venta.cdr_url,
                        "ticket_url": comprobante_venta.ticket_url,
                        "items": comprobante_venta.items
                    }

                productos_json = [
                    {
                        "id": producto.id, # type: ignore
                        "producto": producto.producto.id if producto.producto else None, # type: ignore
                        "producto_nombre": producto.producto.nombre if producto.producto else "Producto eliminado",
                        "cantidad": producto.cantidad,
                        "valor_unitario": float(producto.valor_unitario),
                        "valor_venta": float(producto.valor_venta),
                        "base_igv": float(producto.base_igv),
                        "porcentaje_igv": float(producto.porcentaje_igv),
                        "igv": float(producto.igv),
                        "tipo_afectacion_igv": producto.tipo_afectacion_igv,
                        "total_impuestos": float(producto.total_impuestos),
                        "precio_unitario": float(producto.precio_unitario)
                    }
                    for producto in productos
                ]
                nota_credito = getattr(venta, "nota_credito", None)
                nota_credito_json = None
                if nota_credito:
                    nota_credito_json = {
                        "id": nota_credito.id,
                        "serie": nota_credito.serie,
                        "correlativo": nota_credito.correlativo,
                        "tipo_comprobante_modifica": nota_credito.tipo_comprobante_modifica,
                        "serie_modifica": nota_credito.serie_modifica,
                        "correlativo_modifica": nota_credito.correlativo_modifica,
                        "tipo_motivo": nota_credito.tipo_motivo,
                        "motivo": nota_credito.motivo,
                        "moneda": nota_credito.moneda,
                        "total": float(nota_credito.total),
                        "estado_sunat": nota_credito.estado_sunat,
                        "xml_url": nota_credito.xml_url,
                        "pdf_url": nota_credito.pdf_url,
                        "cdr_url": nota_credito.cdr_url,
                        "fecha_emision": nota_credito.fecha_emision.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                ventas_json.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id,
                    "fecha_hora": venta.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                    "fecha_realizacion": venta.fecha_realizacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "productos": productos_json,
                    "total": venta.total,
                    "subtotal": float(venta.subtotal),
                    "gravado_total": float(venta.gravado_total),
                    "igv_total": float(venta.igv_total),
                    "productos_json": json.dumps(venta.productos_json, indent=4),
                    "comprobante": comprobante_json,
                                        "comprobante_nota_credito":nota_credito_json
                })




            next_page = page_number + 1 if page_number < total_pages else None
            previous_page = page_number - 1 if page_number > 1 else None


            return Response({
                "count": total_ventas,
                "next": next_page,
                "previous": previous_page,
                "index_page": page_number - 1,
                "length_pages": total_pages,
                "results": ventas_json
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)















