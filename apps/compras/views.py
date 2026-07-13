from math import ceil
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.proveedor.models import Proveedor
from .models import ComprobanteCompra


class CompraPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CrearComprobanteCompraView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            tienda = request.user.tienda

            proveedor_data = data.get("proveedor", {})
            proveedor_id = proveedor_data.get("id")
            proveedor = None

            if proveedor_id:
                try:
                    proveedor = Proveedor.objects.get(id=proveedor_id)
                except Proveedor.DoesNotExist:
                    pass

            archivo_xml = request.FILES.get("archivo_xml")
            archivo_pdf = request.FILES.get("archivo_pdf")

            items = data.get("items", [])
            total = Decimal(str(data.get("total", 0)))
            igv = Decimal(str(data.get("igv", 0)))
            gravadas = total - igv

            # Validar que no exista un comprobante con la misma serie y correlativo
            existe = ComprobanteCompra.objects.filter(
                tienda=tienda,
                tipo_comprobante=data["tipo_comprobante"],
                serie=data["serie"],
                correlativo=data["correlativo"],
            ).exists()

            if existe:
                return Response(
                    {"error": f"Ya existe un comprobante con tipo {data['tipo_comprobante']}, serie {data['serie']} y correlativo {data['correlativo']} en esta tienda."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                comprobante = ComprobanteCompra.objects.create(
                    tienda=tienda,
                    proveedor=proveedor,
                    tipo_comprobante=data["tipo_comprobante"],
                    serie=data["serie"],
                    correlativo=data["correlativo"],
                    fecha_emision=data["fecha_emision"],
                    moneda=data.get("moneda", "PEN"),
                    gravadas=gravadas,
                    igv=igv,
                    total=total,
                    tipo_documento_proveedor=proveedor_data.get("tipo_documento", proveedor.ruc if proveedor else None),
                    numero_documento_proveedor=proveedor_data.get("numero_documento", proveedor.ruc if proveedor else None),
                    nombre_proveedor=proveedor_data.get("nombre", proveedor.razon_social if proveedor else None),
                    archivo_xml=archivo_xml,
                    archivo_pdf=archivo_pdf,
                    items=items,
                    observaciones=data.get("observaciones", ""),
                )

            return Response({
                "mensaje": "Comprobante registrado exitosamente",
                "comprobante": {
                    "id": comprobante.id,
                    "tipo_comprobante": comprobante.tipo_comprobante,
                    "serie": comprobante.serie,
                    "correlativo": comprobante.correlativo,
                    "fecha_emision": str(comprobante.fecha_emision),
                    "total": float(comprobante.total),
                    "proveedor": comprobante.nombre_proveedor,
                    "archivo_xml": comprobante.archivo_xml.url if comprobante.archivo_xml else None,
                    "archivo_pdf": comprobante.archivo_pdf.url if comprobante.archivo_pdf else None,
                }
            }, status=status.HTTP_201_CREATED)

        except KeyError as e:
            return Response(
                {"error": f"Falta el campo obligatorio: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ValueError, TypeError) as e:
            return Response(
                {"error": f"Valor inválido: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListaComprobantesCompraView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda_id = request.user.tienda
            page_number = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))

            comprobantes = ComprobanteCompra.objects.filter(tienda_id=tienda_id)

            total = comprobantes.count()
            paginator = CompraPagination()
            result_page = paginator.paginate_queryset(comprobantes, request)
            total_pages = ceil(total / page_size) if page_size > 0 else 0

            next_page = page_number + 1 if page_number < total_pages else None
            previous_page = page_number - 1 if page_number > 1 else None

            comprobantes_json = []
            for c in result_page:
                comprobantes_json.append({
                    "id": c.id,
                    "tipo_comprobante": c.tipo_comprobante,
                    "tipo_comprobante_display": c.get_tipo_comprobante_display(),
                    "serie": c.serie,
                    "correlativo": c.correlativo,
                    "fecha_emision": str(c.fecha_emision),
                    "moneda": c.moneda,
                    "gravadas": float(c.gravadas),
                    "igv": float(c.igv),
                    "total": float(c.total),
                    "proveedor": {
                        "id": c.proveedor.id if c.proveedor else None,
                        "nombre": c.nombre_proveedor,
                        "ruc": c.numero_documento_proveedor,
                    },
                    "archivo_xml": c.archivo_xml.url if c.archivo_xml else None,
                    "archivo_pdf": c.archivo_pdf.url if c.archivo_pdf else None,
                    "items": c.items,
                    "observaciones": c.observaciones,
                    "date_created": c.date_created.isoformat() if c.date_created else None,
                })

            return Response({
                "count": total,
                "next": next_page,
                "previous": previous_page,
                "index_page": page_number - 1,
                "length_pages": total_pages,
                "results": comprobantes_json,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
