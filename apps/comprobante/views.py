import os
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.venta.models import Venta
from apps.comprobante.models import ComprobanteElectronico
from signxml import XMLSigner, methods # type: ignore
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
import base64
import requests
from decimal import Decimal
import xml.dom.minidom as minidom
from lxml import etree # pyright: ignore[reportAttributeAccessIssue]
from bs4 import BeautifulSoup

class GenerarComprobanteView(APIView):
    def post(self, request, venta_id):
        venta = get_object_or_404(Venta, id=venta_id)

   
        return Response({
            'mensaje': 'Comprobante generado',
            'estado_sunat': '',
        }, status=status.HTTP_201_CREATED)


class ListarComprobantesView(APIView):
    def get(self, request):
        comprobantes = ComprobanteElectronico.objects.all()
        return JsonResponse(list(comprobantes), safe=False)


class ConsultaRUCView(APIView):
    def get(self, request, ruc):
        
        return Response({"ruc": ruc, "data": 'ejemplo'}, status=status.HTTP_200_OK)

class ConsultaDNIView(APIView):
    def get(self, request, dni):
               return Response({"dni": dni, "data": "ejemplo"}, status=status.HTTP_200_OK)
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class ConsultaDocumentoView(APIView):
    API_TOKEN = "410e79ed29432fc2d7f215d7563b3e1f6632d7ab6d3a34742949ce00c2acd1d4"
    BASE_URL_DNI = "https://apiperu.dev/api/dni/"
    BASE_URL_RUC = "https://apiperu.dev/api/ruc/"

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

        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response({"error": "No se encontró el documento"}, status=status.HTTP_404_NOT_FOUND)
