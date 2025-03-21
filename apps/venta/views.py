from decimal import Decimal
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

from apps.comprobante.models import ComprobanteElectronico
from apps.inventario.models import Inventario
from .models import Venta, VentaProducto, Tienda, Producto
SUNAT_PHP = "http://localhost:8080"
from django.contrib.auth import get_user_model
User = get_user_model()
from django.db.models import Max


class RegistrarVentaView(APIView):
    def post(self, request):
        try:
            data = request.data

            # Validar que los datos obligatorios existan
            if not all(k in data for k in ["tiendaId", "usuarioId", "metodoPago", "tipoComprobante", "productos"]):
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
            tienda = get_object_or_404(Tienda, id=data["tiendaId"])
            usuario = get_object_or_404(User, id=data["usuarioId"])
            cliente_data = data["cliente"]

            with transaction.atomic():
                # Crear la venta
                venta = Venta.objects.create(
                    usuario=usuario,
                    tienda=tienda,
                    metodo_pago=data["metodoPago"],
                    tipo_comprobante=data["tipoComprobante"]
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
                        precio_unitario=precio_unitario
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
                            "descripcion": producto.descripcion,
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
                php_backend_url_boleta = SUNAT_PHP + "/examples/api/boleta-post.php"
                php_backend_url_factura = SUNAT_PHP + "/examples/api/factura-post.php"
                
                
                headers = {"Content-Type": "application/json"}
                response = requests.post(php_backend_url_factura if data["tipoComprobante"] == "Factura" else php_backend_url_boleta , json=comprobante_data, headers=headers)           
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
                        "productos": productos_registrados,
                        "comprobante_data":comprobante_data ,                
                        "comprobante_result": comprobante_json                 
                    }
                    
                    
                    return Response(venta_json, status=status.HTTP_201_CREATED)
                else:
                    return Response({"error": "Error al generar el comprobante", "detalle": response.text}, status=status.HTTP_400_BAD_REQUEST)
            

        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class VentasPorTiendaView(APIView):
    def get(self, request, tienda_id):
        # Obtener la tienda o devolver 404 si no existe
        tienda = get_object_or_404(Tienda, id=tienda_id)

        # Obtener todas las ventas de la tienda
        ventas = Venta.objects.filter(tienda=tienda)

        # Serializar los datos
        ventas_json = []
        for venta in ventas:
            
            comprobante_venta = ComprobanteElectronico.objects.filter(venta=venta).first()
            
            comprobante_json = None
            productos = VentaProducto.objects.filter(venta=venta)
            if comprobante_venta:
                comprobante_json = {
                "tipo_comprobante": comprobante_venta.tipo_comprobante if comprobante_venta else None,
                "serie": comprobante_venta.serie if comprobante_venta else None,
                "correlativo": comprobante_venta.correlativo if comprobante_venta else None,
                "moneda": comprobante_venta.moneda if comprobante_venta else None,
                "gravadas": float(comprobante_venta.gravadas) if comprobante_venta and comprobante_venta.gravadas else None,
                "igv": float(comprobante_venta.igv) if comprobante_venta and comprobante_venta.igv else None,
                "valorVenta": float(comprobante_venta.valorVenta) if comprobante_venta and comprobante_venta.valorVenta else None,
                "sub_total": float(comprobante_venta.sub_total) if comprobante_venta and comprobante_venta.sub_total else None,
                "total": float(comprobante_venta.total) if comprobante_venta and comprobante_venta.total else None,
                "leyenda": comprobante_venta.leyenda if comprobante_venta else None,
                "tipo_documento_cliente": comprobante_venta.tipo_documento_cliente if comprobante_venta else None,
                "numero_documento_cliente": comprobante_venta.numero_documento_cliente if comprobante_venta else None,
                "nombre_cliente": comprobante_venta.nombre_cliente if comprobante_venta else None,
                "estado_sunat": comprobante_venta.estado_sunat if comprobante_venta else None,
                "xml_url": comprobante_venta.xml_url if comprobante_venta else None,
                "pdf_url": comprobante_venta.pdf_url if comprobante_venta else None,
                "cdr_url": comprobante_venta.cdr_url if comprobante_venta else None,
                "ticket_url": comprobante_venta.ticket_url if comprobante_venta else None,
                "items": comprobante_venta.items if comprobante_venta else None
            }

            productos_json = [
                {
                    "id": producto.id,  # ID del registro en VentaProducto # type: ignore
                    "producto": producto.producto.id if producto.producto else None,  # ID del producto (puede ser nulo) # type: ignore
                    "producto_nombre": producto.producto.nombre if producto.producto else "Producto eliminado",  # Nombre del producto
                    "cantidad": producto.cantidad,
                    "valor_unitario": float(producto.valor_unitario),  # Convertir Decimal a float
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


            ventas_json.append({
                "id": venta.id,   # type: ignore
                "usuario": venta.usuario.id if venta.usuario else None,  # Solo enviamos el ID del usuario
                "tienda": venta.tienda.id,  # Solo enviamos el ID de la tienda # type: ignore
                "fecha_hora": venta.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                "fecha_realizacion": venta.fecha_realizacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_realizacion else None,
                "fecha_cancelacion": venta.fecha_cancelacion.strftime("%Y-%m-%d %H:%M:%S") if venta.fecha_cancelacion else None,
                "metodo_pago": venta.metodo_pago,
                "estado": venta.estado,
                "activo": venta.activo,
                "tipo_comprobante": venta.tipo_comprobante,
                "productos": productos_json,
                "total":venta.total,
                "productos_json" :json.dumps(venta.productos_json, indent=4),
                "comprobante": comprobante_json
            })

        return Response(ventas_json, status=status.HTTP_200_OK)


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