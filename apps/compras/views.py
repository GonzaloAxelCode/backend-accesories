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

from rest_framework.parsers import MultiPartParser, FormParser


from apps.proveedor.models import Proveedor
from .models import ComprobanteCompra, ComprobanteCompraFiles


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


class SubirComprobanteCompraFilesView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            data = request.data
            tienda = request.user.tienda

            tipo_comprobante = data.get("tipo_comprobante")
            if not tipo_comprobante:
                return Response(
                    {"error": "tipo_comprobante es obligatorio (01 o 03)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if tipo_comprobante not in ["01", "03"]:
                return Response(
                    {"error": "tipo_comprobante debe ser '01' (Factura) o '03' (Boleta)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            xml_file = request.FILES.get("xml")
            pdf_file = request.FILES.get("pdf")

            if not xml_file and not pdf_file:
                return Response(
                    {"error": "Debe subir al menos un archivo XML o PDF"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                from django.conf import settings
                import logging
                from django.utils import timezone
                import os
                from botocore.exceptions import ClientError

                logger = logging.getLogger(__name__)

                tienda_nombre = tienda.nombre.strip().lower().replace(" ", "_")
                tipo_nombre = "factura" if tipo_comprobante == "01" else "boleta"
                timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

                xml_url = None
                pdf_url = None

                if settings.DEBUG:
                    from django.core.files.storage import FileSystemStorage

                    fs = FileSystemStorage()
                    base_dir = os.path.join("compras_beta", tienda_nombre, tipo_nombre)

                    if xml_file:
                        ext = os.path.splitext(xml_file.name)[1].lower()
                        if ext != ".xml":
                            return Response(
                                {"error": "El archivo XML debe tener extensión .xml"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        filename = f"xml_{timestamp}{ext}"
                        rel_path = os.path.join(base_dir, filename)
                        fs.save(rel_path, xml_file)
                        xml_url = fs.url(rel_path)
                        logger.info("XML guardado localmente: %s", xml_url)

                    if pdf_file:
                        ext = os.path.splitext(pdf_file.name)[1].lower()
                        if ext != ".pdf":
                            return Response(
                                {"error": "El archivo PDF debe tener extensión .pdf"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        filename = f"pdf_{timestamp}{ext}"
                        rel_path = os.path.join(base_dir, filename)
                        fs.save(rel_path, pdf_file)
                        pdf_url = fs.url(rel_path)
                        logger.info("PDF guardado localmente: %s", pdf_url)
                else:
                    import boto3

                    if not all([
                        settings.R2_ACCOUNT_ID,
                        settings.R2_ACCESS_KEY_ID,
                        settings.R2_SECRET_ACCESS_KEY,
                        settings.R2_BUCKET_NAME,
                        settings.R2_ENDPOINT_URL,
                    ]):
                        logger.error("Configuración R2 incompleta")
                        return Response(
                            {"error": "Configuración de Cloudflare R2 incompleta en el servidor."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    logger.info("Conectando a R2: endpoint=%s, bucket=%s", settings.R2_ENDPOINT_URL, settings.R2_BUCKET_NAME)

                    s3_client = boto3.client(
                        "s3",
                        endpoint_url=settings.R2_ENDPOINT_URL,
                        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                        region_name="auto",
                    )

                    try:
                        s3_client.head_bucket(Bucket=settings.R2_BUCKET_NAME)
                        logger.info("Bucket R2 accesible: %s", settings.R2_BUCKET_NAME)
                    except ClientError as e:
                        logger.error("No se puede acceder al bucket R2: %s", e)
                        return Response(
                            {"error": "No se puede acceder al bucket de R2.", "detalle": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    base_path = f"compras/{tienda_nombre}/{tipo_nombre}"

                    def build_public_url(key):
                        if settings.R2_PUBLIC_URL:
                            return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
                        if settings.R2_ENDPOINT_URL and settings.R2_BUCKET_NAME:
                            endpoint = settings.R2_ENDPOINT_URL.rstrip("/")
                            return f"{endpoint}/{settings.R2_BUCKET_NAME}/{key}"
                        return None

                    if xml_file:
                        ext = os.path.splitext(xml_file.name)[1].lower()
                        if ext != ".xml":
                            return Response(
                                {"error": "El archivo XML debe tener extensión .xml"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        xml_key = f"{base_path}/xml_{timestamp}{ext}"
                        try:
                            s3_client.upload_fileobj(
                                xml_file,
                                settings.R2_BUCKET_NAME,
                                xml_key,
                                ExtraArgs={"ContentType": "application/xml"},
                            )
                            xml_url = build_public_url(xml_key)
                            logger.info("XML subido a R2: %s", xml_url)
                        except ClientError as e:
                            logger.error("Error subiendo XML a R2: %s", e)
                            return Response(
                                {"error": "Error al subir XML a Cloudflare R2", "detalle": str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )

                    if pdf_file:
                        ext = os.path.splitext(pdf_file.name)[1].lower()
                        if ext != ".pdf":
                            return Response(
                                {"error": "El archivo PDF debe tener extensión .pdf"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        pdf_key = f"{base_path}/pdf_{timestamp}{ext}"
                        try:
                            s3_client.upload_fileobj(
                                pdf_file,
                                settings.R2_BUCKET_NAME,
                                pdf_key,
                                ExtraArgs={"ContentType": "application/pdf"},
                            )
                            pdf_url = build_public_url(pdf_key)
                            logger.info("PDF subido a R2: %s", pdf_url)
                        except ClientError as e:
                            logger.error("Error subiendo PDF a R2: %s", e)
                            return Response(
                                {"error": "Error al subir PDF a Cloudflare R2", "detalle": str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )

                if not xml_url and not pdf_url:
                    logger.error("No se generaron URLs para ningún archivo")
                    return Response(
                        {"error": "No se pudo generar URL para ningún archivo."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                registro = ComprobanteCompraFiles.objects.create(
                    tienda=tienda,
                    tipo_comprobante=tipo_comprobante,
                    observaciones=data.get("observaciones"),
                    xml_url=xml_url,
                    pdf_url=pdf_url,
                )

                return Response({
                    "message": "Archivos subidos exitosamente",
                    "data": {
                        "id": registro.id,
                        "tienda": tienda.id,
                        "tipo_comprobante": registro.get_tipo_comprobante_display(),
                        "xml_url": registro.xml_url,
                        "pdf_url": registro.pdf_url,
                        "observaciones": registro.observaciones,
                        "date_created": registro.date_created.isoformat(),
                    }
                }, status=status.HTTP_201_CREATED)

            except ImportError:
                return Response(
                    {"error": "boto3 no está instalado. Ejecuta: pip install boto3"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except ClientError as e:
                return Response(
                    {"error": "Error al subir archivos a Cloudflare R2", "detalle": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListarComprobanteCompraFilesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tipo = request.query_params.get("tipo_comprobante")
            qs = ComprobanteCompraFiles.objects.filter(tienda=tienda)
            if tipo:
                qs = qs.filter(tipo_comprobante=tipo)

            qs = qs.order_by("-date_created")
            data = [
                {
                    "id": r.id,
                    "tienda": r.tienda.id,
                    "tipo_comprobante": r.get_tipo_comprobante_display(),
                    "tipo_comprobante_codigo": r.tipo_comprobante,
                    "xml_url": r.xml_url,
                    "pdf_url": r.pdf_url,
                    "observaciones": r.observaciones,
                    "date_created": r.date_created.isoformat() if r.date_created else None,
                }
                for r in qs
            ]

            return Response({"results": data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
