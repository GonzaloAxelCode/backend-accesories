
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

API_KEY = "f7341ccb912424e7b16b801c35d44014bcb712017be2f209e446233881c096e0"
BASE_URL = "https://api.consultasperu.com/api/v1/query"
HEADERS = {"Content-Type": "application/json"}

class ConsultaDNI(APIView):
    def post(self, request):
        dni = request.data.get("dni")
        if not dni:
            return Response({"success": False, "error": "DNI es requerido"}, status=status.HTTP_400_BAD_REQUEST)
        
        url = BASE_URL
        payload = {
            "token": API_KEY,
            "type_document": "dni",
            "document_number": dni
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS)
            print(response)
            return Response(response.json(), status=response.status_code)
        except requests.exceptions.RequestException:
            return Response({"success": False, "error": "Error en la consulta"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ConsultaRUC(APIView):
    def post(self, request):
        ruc = request.data.get("ruc")
        if not ruc:
            return Response({"success": False, "error": "RUC es requerido"}, status=status.HTTP_400_BAD_REQUEST)
        
        url = BASE_URL
        payload = {
            "token": API_KEY,
            "type_document": "ruc",
            "document_number": ruc
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS)

            print(response)
            return Response(response.json(), status=response.status_code)
        except requests.exceptions.RequestException:
            return Response({"success": False, "error": "Error en la consulta"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
