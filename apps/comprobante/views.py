import os
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.inventario.models import Inventario
from apps.venta.models import Venta, VentaProducto
from apps.comprobante.models import ComprobanteElectronico, NotaCreditoDB
from signxml import XMLSigner, methods # type: ignore
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
import base64
import requests
from decimal import Decimal
import xml.dom.minidom as minidom
from lxml import etree # pyright: ignore[reportAttributeAccessIssue]
from bs4 import BeautifulSoup
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
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.venta.utils import getNextCorrelativo, getNextCorrelativoNotaCredito
from core.permissions import CanCancelSalePermission, CanMakeSalePermission
from core.settings import SUNAT_PHP
from rest_framework.permissions import IsAuthenticated

class ConsultaDocumentoView(APIView):
    API_TOKEN = "7575|WSDJNfDbCzRGohY4KRLEtyjPyjXX0Zm2XXlVR1Sz"
    BASE_URL_DNI = "https://apis.aqpfact.pe/api/dni/"
    BASE_URL_RUC = "https://apis.aqpfact.pe/api/ruc/"

    def post(self, request, *args, **kwargs):
        tipo = request.data.get("tipo")  # "dni" o "ruc"
        numero = request.data.get("numero")

        if not tipo or not numero:
            return Response({"error": "Se requiere 'tipo' y 'numero'"}, status=status.HTTP_400_BAD_REQUEST)

        if tipo == "dni":
            url = f"{self.BASE_URL_DNI}{numero}"
        elif tipo == "ruc":
            url = f"{self.BASE_URL_RUC}{numero}"
        else:
            return Response({"error": "Tipo inválido, usa 'dni' o 'ruc'"}, status=status.HTTP_400_BAD_REQUEST)

        headers = {"Authorization": f"Bearer {self.API_TOKEN}"}
        response = requests.get(url, headers=headers)

        try:
            resp_json = response.json()
        except Exception:
            return Response({"error": "La API no devolvió un JSON válido"}, status=status.HTTP_502_BAD_GATEWAY)

        if resp_json.get("success"):
            data_api = resp_json.get("data", {})

            if tipo == "dni":
                data = {
                    "numero": data_api.get("numero"),
                    "nombre_completo": data_api.get("nombre_completo"),
                    "nombres": data_api.get("nombres"),
                    "apellido_paterno": data_api.get("apellido_paterno"),
                    "apellido_materno": data_api.get("apellido_materno"),
                }
            else:  # ruc
                data = {
                    "numero": data_api.get("ruc"),
                    "nombre_o_razon_social": data_api.get("nombre_o_razon_social"),
                    "nombre_comercial": data_api.get("trade_name") or data_api.get("nombre_comercial", ""),
                    "estado": data_api.get("estado"),
                    "condicion": data_api.get("condicion")
                }

            return Response(data, status=status.HTTP_200_OK)
        else:
            return Response({"error": "No se encontró el documento"}, status=status.HTTP_404_NOT_FOUND)

    """

{
    "success": true,
    "data": {
        "numero": "76881855",
        "nombre_completo": "VALDEZ QUISPE, GONZALO AXEL",
        "name": "VALDEZ QUISPE, GONZALO AXEL",
        "nombres": "GONZALO AXEL",
        "apellido_paterno": "VALDEZ",
        "apellido_materno": "QUISPE",
        "ubigeo": [
            null,
            null,
            null
        ]
    },
    "message": "Datos obtenidos correctamente."
}

{
    "success": true,
    "data": {
        "direccion": "",
        "direccion_completa": " ",
        "ruc": "10768818555",
        "nombre_o_razon_social": "VALDEZ QUISPE GONZALO AXEL",
        "estado": "ACTIVO",
        "condicion": "HABIDO",
        "departamento": "-",
        "provincia": "-",
        "distrito": "-",
        "ubigeo_sunat": "-",
        "name": "VALDEZ QUISPE GONZALO AXEL",
        "trade_name": "",
        "address": " ",
        "ubigeo": [
            null,
            null,
            null
        ],
        "es_agente_de_retencion": "",
        "es_buen_contribuyente": "",
        "state": "ACTIVO"
    },
    "source": "apis.aqpfact.pe"
}
    """
    
   
class RegistrarNotaCreditoView(APIView):
    permission_classes = [IsAuthenticated, CanCancelSalePermission]

    def post(self, request):
        try:
            data = request.data

            # 🔹 Validación básica
            if not all(k in data for k in ["venta_id", "motivo", "tipo_motivo"]):
                return Response(
                    {"error": "Faltan campos obligatorios (venta_id, motivo, tipo_motivo)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            venta = get_object_or_404(Venta, id=data["venta_id"])
            comprobante = get_object_or_404(ComprobanteElectronico, venta=venta)

            # ❌ Evitar anular dos veces
            if venta.estado == "ANULADA":
                return Response(
                    {"error": "La venta ya fue anulada"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 🔹 Evitar duplicar NC
            if NotaCreditoDB.objects.filter(venta=venta).exists():
                return Response(
                    {"error": "Ya existe una nota de crédito para esta venta"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 🔹 Tipo de comprobante afectado
            tipo_comprobante_modifica = (
                "01" if comprobante.tipo_comprobante.lower() == "factura" else "03"
            )

            # 🔹 Serie y correlativo NC (07)
            serie_nc, correlativo_nc = getNextCorrelativoNotaCredito(
                tipo_comprobante_modifica=comprobante.tipo_comprobante.lower()
            )

            fecha_emision = timezone.now()

            # 🔹 Cliente
            if data.get("anonima"):
                cliente = {
                    "tipoDoc": "1",
                    "numDoc": "00000000",
                    "nombre": "CLIENTE ANÓNIMO"
                }
            else:
                cliente = {
                    "tipoDoc": comprobante.tipo_documento_cliente,
                    "numDoc": comprobante.numero_documento_cliente,
                    "nombre": comprobante.nombre_cliente,
                }

            # 🔹 Payload para backend PHP
            comprobante_data = {
                "tipo_comprobante": "07",
                "serie": serie_nc,
                "correlativo": correlativo_nc,
                "fechaEmision": fecha_emision.strftime("%Y-%m-%dT%H:%M:%S"),
                "moneda": comprobante.moneda,
                "total": round(float(comprobante.total or 0), 2),
                "gravadas": round(float(comprobante.gravadas or 0), 2),
                "igv": round(float(comprobante.igv or 0), 2),
                "motivo": data["motivo"],
                "tipo_motivo": data["tipo_motivo"],
                "comprobante_modifica": {
                    "tipo": tipo_comprobante_modifica,
                    "serie": comprobante.serie,
                    "correlativo": comprobante.correlativo,
                },
                "cliente": cliente,
                "items": comprobante.items,
            }

            php_backend_url = f"{SUNAT_PHP}/src/api/nota-credito-post.php"
            response = requests.post(
                php_backend_url,
                json=comprobante_data,
                headers={"Content-Type": "application/json"},
                timeout=20
            )

            if response.status_code != 200:
                return Response(
                    {"error": "Error al enviar NC al backend PHP", "detalle": response.text},
                    status=status.HTTP_400_BAD_REQUEST
                )

            response_json = response.json()
            estado_sunat = "Aceptado" if response_json.get("cdr_codigo") == "0" else "Rechazado"

            if estado_sunat == "Rechazado":
                return Response(
                    {
                        "error": "SUNAT rechazó la nota de crédito",
                        "sunat_response": response_json
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 🔹 Guardar NC + devolver stock + anular venta
            with transaction.atomic():

                # ✅ Crear Nota de Crédito
                nota = NotaCreditoDB.objects.create(
                    venta=venta,
                    comprobante_modificado=comprobante,
                    serie=serie_nc,
                    correlativo=correlativo_nc,
                    tipo_comprobante_modifica=tipo_comprobante_modifica,
                    serie_modifica=comprobante.serie,
                    correlativo_modifica=comprobante.correlativo,
                    tipo_motivo=data["tipo_motivo"],
                    motivo=data["motivo"],
                    total=comprobante.total,
                    estado_sunat=estado_sunat,
                    xml_url=response_json.get("xml_url"),
                    pdf_url=response_json.get("pdf_url"),
                    cdr_url=response_json.get("cdr_url"),
                )

                # 🔁 DEVOLVER STOCK
                productos_vendidos = VentaProducto.objects.select_for_update().filter(
                    venta=venta
                )

                for vp in productos_vendidos:
                    inventario = Inventario.objects.select_for_update().filter(
                        producto=vp.producto,
                        tienda=venta.tienda,
                        activo=True
                    ).first()

                    if inventario:
                        inventario.cantidad += vp.cantidad
                        inventario.save(update_fields=["cantidad"])

                # ❌ Anular venta
                venta.estado = "ANULADA"
                venta.save(update_fields=["estado"])

            # 🔹 RESPUESTA FINAL
            return Response(
                {
                    "comprobante_nota_credito": {
                        "id": nota.id, # type: ignore
                        "serie": nota.serie,
                        "correlativo": nota.correlativo,
                        "tipo_comprobante_modifica": nota.tipo_comprobante_modifica,
                        "serie_modifica": nota.serie_modifica,
                        "correlativo_modifica": nota.correlativo_modifica,
                        "tipo_motivo": nota.tipo_motivo,
                        "motivo": nota.motivo,
                        "moneda": comprobante.moneda,
                        "total": float(nota.total),
                        "estado_sunat": nota.estado_sunat,
                        "xml_url": nota.xml_url,
                        "pdf_url": nota.pdf_url,
                        "cdr_url": nota.cdr_url,
                        "fecha_emision": fecha_emision,
                    },
                    "venta_estado": venta.estado,
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
