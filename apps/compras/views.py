from math import ceil
from decimal import Decimal
import re

from django.db import transaction
from django.db.models import Q
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

            # ============================================
            # VALIDACIONES DE CAMPOS OBLIGATORIOS
            # ============================================
            errores = []

            tipo_comprobante = data.get("tipo_comprobante")
            if not tipo_comprobante:
                errores.append("tipo_comprobante es obligatorio")
            elif tipo_comprobante not in ["01", "03"]:
                errores.append("tipo_comprobante debe ser '01' (Factura) o '03' (Boleta)")

            serie = data.get("serie")
            if not serie:
                errores.append("serie es obligatoria")

            correlativo = data.get("correlativo")
            if not correlativo:
                errores.append("correlativo es obligatorio")

            fecha_emision = data.get("fecha_emision")
            if not fecha_emision:
                errores.append("fecha_emision es obligatoria")

            items = data.get("items", [])
            if not items or len(items) == 0:
                errores.append("Debe incluir al menos un item")

            if errores:
                return Response(
                    {"error": "Campos obligatorios faltantes", "detalles": errores},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ============================================
            # VERIFICAR DUPLICADOS
            # ============================================
            existe = ComprobanteCompra.objects.filter(
                tienda=tienda,
                tipo_comprobante=tipo_comprobante,
                serie=serie.strip().upper(),
                correlativo=correlativo.strip(),
            ).exists()

            if existe:
                return Response(
                    {
                        "error": "Comprobante duplicado",
                        "detalle": f"Ya existe un comprobante con tipo {tipo_comprobante}, serie {serie} y correlativo {correlativo} en esta tienda."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ============================================
            # PROCESAR PROVEEDOR
            # ============================================
            proveedor_data = data.get("proveedor", {})
            proveedor = None

            # Buscar proveedor por ID
            proveedor_id = proveedor_data.get("id")
            if proveedor_id:
                try:
                    proveedor = Proveedor.objects.get(id=proveedor_id, tienda=tienda)
                except Proveedor.DoesNotExist:
                    return Response(
                        {"error": f"Proveedor con ID {proveedor_id} no encontrado en esta tienda."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Datos del proveedor para guardar en el comprobante
            nombre_proveedor = proveedor_data.get("nombre") or (proveedor.razon_social if proveedor else None)
            tipo_doc_proveedor = proveedor_data.get("tipo_documento") or (proveedor.ruc[:1] if proveedor and proveedor.ruc else None)
            num_doc_proveedor = proveedor_data.get("numero_documento") or (proveedor.ruc if proveedor else None)

            # ============================================
            # PROCESAR ARCHIVOS
            # ============================================
            archivo_xml = request.FILES.get("archivo_xml")
            archivo_pdf = request.FILES.get("archivo_pdf")

            # Validar extensiones
            if archivo_xml and not archivo_xml.name.endswith('.xml'):
                return Response(
                    {"error": "El archivo XML debe tener extensión .xml"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if archivo_pdf and not archivo_pdf.name.endswith('.pdf'):
                return Response(
                    {"error": "El archivo PDF debe tener extensión .pdf"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ============================================
            # CALCULAR MONTOS
            # ============================================
            # Si el cliente envía total e igv, se usan esos valores
            # Si no, se calculan desde los items
            total_enviado = data.get("total")
            igv_enviado = data.get("igv")

            if total_enviado is not None and igv_enviado is not None:
                total = Decimal(str(total_enviado))
                igv = Decimal(str(igv_enviado))
                gravadas = total - igv
            else:
                # Calcular desde items
                gravadas = Decimal("0")
                for item in items:
                    cantidad = Decimal(str(item.get("cantidad", 0)))
                    precio = Decimal(str(item.get("precio_unitario", 0)))
                    descuento = Decimal(str(item.get("descuento", 0)))
                    gravadas += (cantidad * precio) - descuento

                gravadas = gravadas.quantize(Decimal("0.01"))
                igv = (gravadas * Decimal("0.18")).quantize(Decimal("0.01"))
                total = gravadas + igv

            # ============================================
            # VALORES POR DEFECTO
            # ============================================
            moneda = data.get("moneda", "PEN")
            forma_pago = data.get("forma_pago", "CONTADO")
            fecha_vencimiento = data.get("fecha_vencimiento")
            op_exoneradas = Decimal(str(data.get("op_exoneradas", 0)))
            op_inafectas = Decimal(str(data.get("op_inafectas", 0)))
            op_gratuitas = Decimal(str(data.get("op_gratuitas", 0)))
            dctos_totales = Decimal(str(data.get("dctos_totales", 0)))
            icbper = Decimal(str(data.get("icbper", 0)))
            documento_relacionado = data.get("documento_relacionado")
            enlace_verificacion = data.get("enlace_verificacion")
            observaciones = data.get("observaciones", "")

            # ============================================
            # CREAR COMPROBANTE
            # ============================================
            with transaction.atomic():
                comprobante = ComprobanteCompra.objects.create(
                    tienda=tienda,
                    proveedor=proveedor,
                    tipo_comprobante=tipo_comprobante,
                    serie=serie.strip().upper(),
                    correlativo=correlativo.strip(),
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_vencimiento,
                    forma_pago=forma_pago,
                    moneda=moneda,
                    gravadas=gravadas,
                    op_exoneradas=op_exoneradas,
                    op_inafectas=op_inafectas,
                    op_gratuitas=op_gratuitas,
                    dctos_totales=dctos_totales,
                    icbper=icbper,
                    igv=igv,
                    total=total,
                    tipo_documento_proveedor=tipo_doc_proveedor,
                    numero_documento_proveedor=num_doc_proveedor,
                    nombre_proveedor=nombre_proveedor,
                    documento_relacionado=documento_relacionado,
                    enlace_verificacion=enlace_verificacion,
                    archivo_xml=archivo_xml,
                    archivo_pdf=archivo_pdf,
                    items=items,
                    observaciones=observaciones,
                )

            return Response({
                "mensaje": "Comprobante registrado exitosamente",
                "comprobante": {
                    "id": comprobante.id,
                    "tipo_comprobante": comprobante.tipo_comprobante,
                    "tipo_comprobante_display": comprobante.get_tipo_comprobante_display(),
                    "serie": comprobante.serie,
                    "correlativo": comprobante.correlativo,
                    "fecha_emision": str(comprobante.fecha_emision),
                    "fecha_vencimiento": str(comprobante.fecha_vencimiento) if comprobante.fecha_vencimiento else None,
                    "forma_pago": comprobante.forma_pago,
                    "moneda": comprobante.moneda,
                    "gravadas": float(comprobante.gravadas),
                    "igv": float(comprobante.igv),
                    "total": float(comprobante.total),
                    "proveedor": {
                        "id": comprobante.proveedor.id if comprobante.proveedor else None,
                        "nombre": comprobante.nombre_proveedor,
                        "ruc": comprobante.numero_documento_proveedor,
                    },
                    "items": comprobante.items,
                    "archivo_xml": comprobante.archivo_xml.url if comprobante.archivo_xml else None,
                    "archivo_pdf": comprobante.archivo_pdf.url if comprobante.archivo_pdf else None,
                    "observaciones": comprobante.observaciones,
                    "date_created": comprobante.date_created.isoformat() if comprobante.date_created else None,
                }
            }, status=status.HTTP_201_CREATED)

        except KeyError as e:
            return Response(
                {"error": f"Falta el campo obligatorio: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ValueError, TypeError, Decimal.InvalidOperation) as e:
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
            tienda = request.user.tienda

            # ----- Parámetros de filtro -----
            query = request.query_params
            nombre = (query.get("nombre") or "").strip().lower()
            nombre_normalizado = re.sub(r"\s+", " ", nombre).strip()

            tipo_comprobante = query.get("tipo_comprobante")
            serie = (query.get("serie") or "").strip()
            correlativo = (query.get("correlativo") or "").strip()
            moneda = query.get("moneda")
            forma_pago = query.get("forma_pago")
            proveedor_nombre = (query.get("proveedor") or "").strip().lower()

            # --- Filtros de fecha ---
            fecha_desde = query.get("fecha_desde")
            fecha_hasta = query.get("fecha_hasta")

            # --- Filtros de monto ---
            total_min = query.get("total_min")
            total_max = query.get("total_max")

            # ----- Construir filtros -----
            filtros = Q(tienda=tienda)

            if nombre_normalizado:
                palabras = nombre_normalizado.split(" ")
                for palabra in palabras:
                    filtros &= (
                        Q(serie__icontains=palabra) |
                        Q(correlativo__icontains=palabra) |
                        Q(nombre_proveedor__icontains=palabra) |
                        Q(numero_documento_proveedor__icontains=palabra) |
                        Q(observaciones__icontains=palabra)
                    )

            if tipo_comprobante:
                filtros &= Q(tipo_comprobante=tipo_comprobante)

            if serie:
                filtros &= Q(serie__icontains=serie)

            if correlativo:
                filtros &= Q(correlativo__icontains=correlativo)

            if moneda:
                filtros &= Q(moneda=moneda)

            if forma_pago:
                filtros &= Q(forma_pago=forma_pago)

            if proveedor_nombre:
                filtros &= Q(nombre_proveedor__icontains=proveedor_nombre)

            # --- Rango de fechas ---
            if fecha_desde:
                try:
                    filtros &= Q(fecha_emision__gte=fecha_desde)
                except ValueError:
                    pass

            if fecha_hasta:
                try:
                    filtros &= Q(fecha_emision__lte=fecha_hasta)
                except ValueError:
                    pass

            # --- Rango de montos ---
            if total_min is not None:
                try:
                    filtros &= Q(total__gte=float(total_min))
                except ValueError:
                    pass

            if total_max is not None:
                try:
                    filtros &= Q(total__lte=float(total_max))
                except ValueError:
                    pass

            # ----- Query -----
            comprobantes = ComprobanteCompra.objects.filter(filtros).order_by("-date_created")
            total = comprobantes.count()

            if total == 0:
                return Response({
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "index_page": 1,
                    "length_pages": 0,
                    "results": [],
                    "search_found": "not_found"
                })

            # ----- Paginación -----
            paginator = CompraPagination()
            result_page = paginator.paginate_queryset(comprobantes, request)

            comprobantes_json = []
            for c in result_page:
                comprobantes_json.append({
                    "id": c.id,
                    "tipo_comprobante": c.tipo_comprobante,
                    "tipo_comprobante_display": c.get_tipo_comprobante_display(),
                    "serie": c.serie,
                    "correlativo": c.correlativo,
                    "fecha_emision": str(c.fecha_emision),
                    "fecha_vencimiento": str(c.fecha_vencimiento) if c.fecha_vencimiento else None,
                    "forma_pago": c.forma_pago,
                    "moneda": c.moneda,
                    "gravadas": float(c.gravadas),
                    "op_exoneradas": float(c.op_exoneradas),
                    "op_inafectas": float(c.op_inafectas),
                    "op_gratuitas": float(c.op_gratuitas),
                    "dctos_totales": float(c.dctos_totales),
                    "icbper": float(c.icbper),
                    "igv": float(c.igv),
                    "total": float(c.total),
                    "proveedor": {
                        "id": c.proveedor.id if c.proveedor else None,
                        "nombre": c.nombre_proveedor,
                        "ruc": c.numero_documento_proveedor,
                        "tipo_documento": c.tipo_documento_proveedor,
                    },
                    "documento_relacionado": c.documento_relacionado,
                    "enlace_verificacion": c.enlace_verificacion,
                    "archivo_xml": c.archivo_xml.url if c.archivo_xml else None,
                    "archivo_pdf": c.archivo_pdf.url if c.archivo_pdf else None,
                    "items": c.items,
                    "observaciones": c.observaciones,
                    "date_created": c.date_created.isoformat() if c.date_created else None,
                })

            pg = paginator.page

            return Response({
                "count": total,
                "next": pg.next_page_number() if pg.has_next() else None,
                "previous": pg.previous_page_number() if pg.has_previous() else None,
                "index_page": pg.number,
                "length_pages": pg.paginator.num_pages,
                "results": comprobantes_json,
                "search_found": "found"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
