import logging
import re
import xml.etree.ElementTree as ET
from math import ceil

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from core.permissions import PuedeActualizarCompra, PuedeCrearCompra, PuedeEliminarCompra

from apps.proveedor.models import Proveedor
from .models import ComprobanteCompra
from .serializers import ComprobanteCompraSerializer

logger = logging.getLogger(__name__)

# Extensiones permitidas por kind en POST compras/<id>/archivos/
ARCHIVOS_PERMITIDOS = {
    "pdf": (".pdf", "application/pdf"),
    "xml": (".xml", "application/xml"),
}


def _sanear_segmento(nombre, default="tienda"):
    limpio = re.sub(r"[^a-z0-9_-]+", "_", (nombre or default).strip().lower().replace(" ", "_"))
    limpio = re.sub(r"_+", "_", limpio).strip("_")
    return limpio or default


def _r2_client():
    import boto3

    if not all([
        getattr(settings, "R2_ACCESS_KEY_ID", None),
        getattr(settings, "R2_SECRET_ACCESS_KEY", None),
        getattr(settings, "R2_BUCKET_NAME", None),
        getattr(settings, "R2_ENDPOINT_URL", None),
    ]):
        raise RuntimeError("Configuración de Cloudflare R2 incompleta en el servidor.")
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL.rstrip("/"),
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _r2_public_url(key):
    if getattr(settings, "R2_PUBLIC_URL", None):
        return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
    return f"{settings.R2_ENDPOINT_URL.rstrip('/')}/{settings.R2_BUCKET_NAME}/{key}"


def _r2_key_desde_url(url):
    """Extrae el key R2 desde una URL pública guardada. None si no es extraíble."""
    if not url:
        return None
    base = (getattr(settings, "R2_PUBLIC_URL", "") or "").rstrip("/")
    if base and url.startswith(base + "/"):
        return url[len(base) + 1:]
    marker = "/" + (getattr(settings, "R2_BUCKET_NAME", "") or "") + "/"
    if marker.strip("/") and marker in url:
        return url.split(marker, 1)[1]
    return None


def _carpeta_r2_compra(compra):
    """Key-prefijo de la carpeta R2 del comprobante (sin la base pública)."""
    if compra.xml_constancia:
        key = _r2_key_desde_url(compra.xml_constancia)
        if key and "/" in key:
            return key.rsplit("/", 1)[0]
    tienda = _sanear_segmento(getattr(compra.tienda, "nombre", None))
    base = "BETA" if getattr(settings, "DEBUG", False) else ""
    periodo = (compra.date_created or timezone.now()).strftime("%Y-%m")
    base_id = f"{compra.ruc_proveedor}-{compra.tipo_comprobante}-{compra.serie}-{compra.correlativo}"
    prefijo = f"{base}/" if base else ""
    return f"{prefijo}{tienda}/compras/{periodo}/{base_id}"


def _localname(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _normalizar_correlativo(valor):
    v = str(valor or "").strip()
    return str(int(v)) if v.isdigit() else v.upper()


def _extraer_datos_xml_compra(content):
    """RUC emisor + serie/correlativo + total desde un XML UBL (búsqueda por nombre local, sin namespaces)."""
    from decimal import Decimal, InvalidOperation

    root = ET.fromstring(content)
    if _localname(root.tag) not in ("Invoice", "CreditNote", "DebitNote"):
        raise ValueError("El XML no es un comprobante electrónico (Invoice/CreditNote/DebitNote)")

    numero = None
    for child in root:
        if _localname(child.tag) == "ID" and (child.text or "").strip():
            numero = child.text.strip()
            break
    if not numero or "-" not in numero:
        raise ValueError("No se pudo leer serie-correlativo del XML")

    serie, correlativo = numero.split("-", 1)
    ruc = None
    for el in root.iter():
        if _localname(el.tag) == "AccountingSupplierParty":
            party = next((c for c in el if _localname(c.tag) == "Party"), None)
            if party is None:
                break
            # PartyIdentification/ID (schemeID=6) o EndpointID como respaldo
            for c in party.iter():
                if _localname(c.tag) == "ID" and (c.text or "").strip().isdigit():
                    ruc = c.text.strip()
                    if c.get("schemeID") == "6" or len(ruc) == 11:
                        break
            if ruc is None:
                for c in party.iter():
                    if _localname(c.tag) == "EndpointID" and (c.text or "").strip():
                        ruc = c.text.strip()
                        break
            break
    if not ruc:
        raise ValueError("No se pudo leer el RUC del emisor del XML")

    total = None
    for el in root.iter():
        if _localname(el.tag) == "PayableAmount" and (el.text or "").strip():
            try:
                total = Decimal(el.text.strip())
            except InvalidOperation:
                total = None
            break
    return ruc, serie.strip().upper(), correlativo.strip(), total


def _resolver_ruc_proveedor(tienda, data, proveedor):
    """RUC emisor: del proveedor vinculado o del campo directo."""
    if proveedor and proveedor.ruc:
        return str(proveedor.ruc).strip()
    ruc = data.get("rucProveedor", data.get("ruc_proveedor", ""))
    return str(ruc or "").strip() or None


class GuardarCompraView(APIView):
    """Guarda el registro mínimo de una compra ya validada en SUNAT.

    Flujo Angular: 1) POST comprobante/compra/guardar/ -> xml_url,
    2) POST compras/guardar/ con los mismos datos + xml_url.
    """

    permission_classes = [IsAuthenticated, PuedeCrearCompra]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        tienda = request.user.tienda

        proveedor = None
        proveedor_id = data.get("proveedor_id", data.get("proveedor"))
        if isinstance(proveedor_id, dict):
            proveedor_id = proveedor_id.get("id")
        if proveedor_id:
            try:
                proveedor = Proveedor.objects.get(id=proveedor_id, tienda=tienda)
            except (Proveedor.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"error": f"Proveedor con ID {proveedor_id} no encontrado en esta tienda."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ruc_proveedor = _resolver_ruc_proveedor(tienda, data, proveedor)
        if not ruc_proveedor:
            # Intento de auto-vínculo por RUC ya resuelto arriba; si no hay, error.
            pass

        payload = {
            "proveedor": proveedor.id if proveedor else None,
            "ruc_proveedor": ruc_proveedor,
            "tipo_comprobante": data.get("tipo_comprobante", data.get("tipoDoc")),
            "serie": data.get("serie"),
            "correlativo": data.get("correlativo"),
            "total": data.get("total") if data.get("total") not in (None, "") else "0.00",
            "xml_constancia": data.get("xml_constancia", data.get("xml_url")),
            "xml_comprobante": data.get("xml_comprobante"),
            "pdf_url": data.get("pdf_url"),
            "estado_codigo": data.get("estado_codigo", data.get("cdr_codigo")),
            "estado_descripcion": data.get("estado_descripcion", data.get("cdr_descripcion")),
        }

        serializer = ComprobanteCompraSerializer(data=payload)
        if not serializer.is_valid():
            return Response(
                {"error": "Datos inválidos", "detalles": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not serializer.validated_data.get("ruc_proveedor"):
            return Response({"error": "rucProveedor debe tener 11 dígitos"}, status=status.HTTP_400_BAD_REQUEST)
        if not serializer.validated_data.get("xml_constancia"):
            return Response({"error": "xml_constancia es obligatorio (valida primero en SUNAT)"}, status=status.HTTP_400_BAD_REQUEST)

        # Auto-vincula proveedor por RUC si no se envió proveedor_id.
        if proveedor is None and serializer.validated_data.get("ruc_proveedor"):
            proveedor = Proveedor.objects.filter(
                tienda=tienda, ruc=serializer.validated_data["ruc_proveedor"], activo=True
            ).first()

        try:
            compra = serializer.save(tienda=tienda, proveedor=proveedor)
        except IntegrityError:
            return Response(
                {"error": "Comprobante duplicado", "detalle": "Ya existe esa compra en esta tienda."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"mensaje": "Compra guardada", "comprobante": ComprobanteCompraSerializer(compra).data},
            status=status.HTTP_201_CREATED,
        )


class ListaComprasView(APIView):
    """Consulta compras guardadas. GET /api/compras/lista/?page=1&page_size=5&q=F001"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = request.user.tienda
        qs = ComprobanteCompra.objects.filter(tienda=tienda).select_related("proveedor")

        q = (request.query_params.get("q") or request.query_params.get("search") or "").strip()
        if q:
            qs = qs.filter(
                Q(serie__icontains=q)
                | Q(correlativo__icontains=q)
                | Q(ruc_proveedor__icontains=q)
                | Q(estado_descripcion__icontains=q)
            )

        tipo = (request.query_params.get("tipo_comprobante") or "").strip()
        if tipo:
            qs = qs.filter(tipo_comprobante__iexact=tipo)

        numero = (request.query_params.get("numero_comprobante") or "").replace(" ", "")
        if numero:
            if "-" in numero:
                serie_part, corr_part = numero.split("-", 1)
                if serie_part:
                    qs = qs.filter(serie__iexact=serie_part)
                if corr_part:
                    qs = qs.filter(correlativo__icontains=corr_part)
            else:
                qs = qs.filter(Q(serie__icontains=numero) | Q(correlativo__icontains=numero))

        proveedor_id = request.query_params.get("proveedor_id")
        if proveedor_id:
            try:
                qs = qs.filter(proveedor_id=int(proveedor_id))
            except (ValueError, TypeError):
                pass

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", 5)), 1), 100)
        except (ValueError, TypeError):
            page_size = 5

        total = qs.count()
        total_pages = ceil(total / page_size) if total else 0
        if total_pages and page > total_pages:
            page = total_pages
        inicio = (page - 1) * page_size
        items = list(qs[inicio:inicio + page_size])

        return Response(
            {
                "count": total,
                "next": page + 1 if total_pages and page < total_pages else None,
                "previous": page - 1 if page > 1 else None,
                "index_page": page - 1,
                "length_pages": total_pages,
                "results": ComprobanteCompraSerializer(items, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class DetalleCompraView(APIView):
    """Consulta una compra guardada por id."""

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        compra = get_object_or_404(ComprobanteCompra, id=id, tienda=request.user.tienda)
        return Response(ComprobanteCompraSerializer(compra).data, status=status.HTTP_200_OK)


class EliminarCompraView(APIView):
    """Elimina el registro local. Los archivos en R2 se conservan como sustento."""

    permission_classes = [IsAuthenticated, PuedeEliminarCompra]

    def delete(self, request, id):
        compra = get_object_or_404(ComprobanteCompra, id=id, tienda=request.user.tienda)
        compra.delete()
        return Response({"mensaje": "Compra eliminada"}, status=status.HTTP_200_OK)


class ActualizarArchivosCompraView(APIView):
    """Sube archivos a R2: el `pdf` se puede reemplazar siempre; el `xml`
    solo se acepta si el registro aún no tiene (queda fijo al registrar).

    POST multipart compras/<id>/archivos/ con files `pdf` y/o `xml`.
    El XML se valida: debe corresponder al mismo RUC/serie/correlativo/total.
    """

    permission_classes = [IsAuthenticated, PuedeActualizarCompra]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, id):
        compra = get_object_or_404(ComprobanteCompra, id=id, tienda=request.user.tienda)

        pdf = request.FILES.get("pdf")
        xml = request.FILES.get("xml", request.FILES.get("xml_comprobante"))
        if not pdf and not xml:
            return Response(
                {"error": "Envía al menos un archivo: `pdf` y/o `xml`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for archivo, kind in ((pdf, "pdf"), (xml, "xml")):
            if archivo and not archivo.name.lower().endswith(ARCHIVOS_PERMITIDOS[kind][0]):
                return Response(
                    {"error": f"El archivo {kind} debe tener extensión {ARCHIVOS_PERMITIDOS[kind][0]}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if xml and compra.xml_comprobante:
            return Response(
                {"error": "El XML del comprobante ya está registrado y no se puede modificar"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if xml:
            try:
                ruc_xml, serie_xml, corr_xml, total_xml = _extraer_datos_xml_compra(xml.read())
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                logger.exception("Error parseando XML de compra %s", compra.id)
                return Response({"error": "No se pudo leer el XML"}, status=status.HTTP_400_BAD_REQUEST)
            if (ruc_xml != (compra.ruc_proveedor or "")
                    or serie_xml != (compra.serie or "")
                    or _normalizar_correlativo(corr_xml) != _normalizar_correlativo(compra.correlativo)):
                return Response(
                    {
                        "error": "El XML no corresponde a este comprobante",
                        "detalle": f"XML: {ruc_xml} {serie_xml}-{corr_xml} / registro: {compra.ruc_proveedor} {compra.serie}-{compra.correlativo}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from decimal import Decimal as _Decimal
            if total_xml is not None and compra.total:
                try:
                    if abs(_Decimal(total_xml) - compra.total) > _Decimal("0.01"):
                        return Response(
                            {
                                "error": "El total del XML no coincide con el registrado",
                                "detalle": f"XML: {total_xml} / registro: {compra.total}",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                except Exception:
                    pass
            xml.seek(0)

        try:
            cliente_r2 = _r2_client()
            carpeta = _carpeta_r2_compra(compra)
            base = f"{compra.serie}-{compra.correlativo}"

            if pdf:
                key_pdf = f"{carpeta}/{base}.pdf"
                cliente_r2.upload_fileobj(
                    pdf, settings.R2_BUCKET_NAME, key_pdf,
                    ExtraArgs={"ContentType": ARCHIVOS_PERMITIDOS["pdf"][1]},
                )
                compra.pdf_url = _r2_public_url(key_pdf)

            if xml:
                key_xml = f"{carpeta}/{base}-comprobante.xml"
                cliente_r2.upload_fileobj(
                    xml, settings.R2_BUCKET_NAME, key_xml,
                    ExtraArgs={"ContentType": ARCHIVOS_PERMITIDOS["xml"][1]},
                )
                compra.xml_comprobante = _r2_public_url(key_xml)

            compra.save(update_fields=["pdf_url", "xml_comprobante"])
        except RuntimeError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception("Error subiendo archivos de compra %s a R2", compra.id)
            return Response({"error": "Error al subir a R2", "detalle": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {"mensaje": "Archivos actualizados", "comprobante": ComprobanteCompraSerializer(compra).data},
            status=status.HTTP_200_OK,
        )
