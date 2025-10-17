import os
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.venta.models import Venta
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
            if "venta_id" not in data or "motivo" not in data or "tipo_motivo" not in data:
                return Response(
                    {"error": "Faltan campos obligatorios (venta_id, motivo, tipo_motivo)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            venta = get_object_or_404(Venta, id=data["venta_id"])
            comprobante = get_object_or_404(ComprobanteElectronico, venta=venta)

            # 🔹 Evitar duplicar notas
            if NotaCreditoDB.objects.filter(venta=venta).exists():
                return Response(
                    {"error": f"Ya existe una nota de crédito para la venta "},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determinar tipo de documento que se modifica
            tipo_comprobante_modifica = "01" if comprobante.tipo_comprobante.lower() == "factura" else "03"

            # Determinar serie de la Nota de Crédito según el tipo de comprobante original
            # Si fue factura → serie de NC empieza con F
            # Si fue boleta → serie de NC empieza con B
            if tipo_comprobante_modifica == "01":
                serie_nc = "F001"  # Nota de crédito para factura
            else:
                serie_nc = "B001"  # Nota de crédito para boleta
            ultima_nc = NotaCreditoDB.objects.order_by("-id").first()
            correlativo_nc = str(int(ultima_nc.correlativo) + 1).zfill(8) if ultima_nc else "00000001"

            fecha_emision = timezone.now()

            # 🔹 JSON a enviar al backend PHP
            comprobante_data = {
                "tipo_comprobante": "07",
                "serie": serie_nc,
                "correlativo": correlativo_nc,
                "fechaEmision": fecha_emision.strftime("%Y-%m-%dT%H:%M:%S"),
                "moneda": comprobante.moneda,
                "total": round(float(comprobante.total or 0)),
                "gravadas": round(float(comprobante.gravadas or 0)),
                "igv": round(float(comprobante.igv or 0)),
                "motivo": data["motivo"],
                "tipo_motivo": data["tipo_motivo"],
                "comprobante_modifica": {
                    "tipo": tipo_comprobante_modifica,
                    "serie": comprobante.serie,
                    "correlativo": comprobante.correlativo,
                },
                "cliente": {
                    "tipoDoc": comprobante.tipo_documento_cliente,
                    "numDoc": comprobante.numero_documento_cliente,
                    "nombre": comprobante.nombre_cliente,
                },
                "items": comprobante.items,
            }
            print(comprobante_data)
            # 🔹 Enviar a backend PHP
            php_backend_url = f"{SUNAT_PHP}/src/api/nota-credito-post.php"
            headers = {"Content-Type": "application/json"}
            response = requests.post(php_backend_url, json=comprobante_data, headers=headers)

            if response.status_code != 200:
                print(response)
                return Response(
                    {"error": "Error al enviar la nota de crédito al backend PHP" + str(response.text)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            response_json = response.json()
            estado_sunat = "Aceptado" if response_json.get("cdr_codigo") == "0" else "Rechazado"

            # 🔹 Si SUNAT la rechazó → no guardar nada
            if estado_sunat == "Rechazado":
                return Response({
                    "error": "SUNAT rechazó la nota de crédito",
                    "sunat_response": response_json
                }, status=status.HTTP_400_BAD_REQUEST)

            # 🔹 Crear registro local en BD solo si fue aceptada
            with transaction.atomic():
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

                # 🔹 Marcar la venta como ANULADA
                venta.estado = "ANULADA"
                venta.save(update_fields=["estado"])

            # 🔹 Respuesta final
            return Response({
                "message": "Nota de crédito generada y aceptada por SUNAT",
                "nota_credito": {
                    "serie": nota.serie,
                    "correlativo": nota.correlativo,
                    "estado_sunat": nota.estado_sunat,
                    "xml_url": nota.xml_url,
                    "pdf_url": nota.pdf_url,
                    "cdr_url": nota.cdr_url,
                },
                "venta_estado": venta.estado,
                "sunat_response": response_json
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
