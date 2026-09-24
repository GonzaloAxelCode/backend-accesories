import json
import logging
import os
import re
from decimal import Decimal
from math import ceil

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.proveedor.models import Proveedor
from .models import ComprobanteCompra

logger = logging.getLogger(__name__)


class CompraPagination(PageNumberPagination):
    # Igual que ventas: VentaPagination
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------------------------------------------------------------------------
# Storage R2 — SIEMPRE (debug y producción). Estructura de keys:
#   {BETA_COMPRAS|PRODUCCION_COMPRAS}/{tienda}/compra{id}-{yyyymmdd_hhmmss}/
#       compra-{factura|boleta}-{yyyy-mm-dd}-{xml|pdf|imagen}.{ext}
# Devuelve las URLs públicas que se guardan en xml_url / pdf_url / image_url.
# ---------------------------------------------------------------------------
R2_BASE_DEBUG = "BETA_COMPRAS"
R2_BASE_PROD = "PRODUCCION_COMPRAS"

R2_CONTENT_TYPES = {
    ".xml": "application/xml",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

ARCHIVOS_COMPRA = {
    # kind: (aliases de request.FILES, extensiones permitidas)
    "xml": (("xml", "archivo_xml"), [".xml"]),
    "pdf": (("pdf", "archivo_pdf"), [".pdf"]),
    "imagen": (("imagen", "image", "foto", "archivo_imagen"), [".jpg", ".jpeg", ".png", ".webp"]),
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

    endpoint = (settings.R2_ENDPOINT_URL or "").strip().rstrip("/")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def build_compra_r2_key(*, debug, tienda_nombre, compra_id, date_created, tipo_comprobante, kind, ext):
    """Construye el key R2 de un archivo de compra (función pura, testeable)."""
    base = R2_BASE_DEBUG if debug else R2_BASE_PROD
    tienda = _sanear_segmento(tienda_nombre)
    fecha_hora = date_created.strftime("%Y%m%d_%H%M%S") if date_created else timezone.now().strftime("%Y%m%d_%H%M%S")
    fecha = date_created.strftime("%Y-%m-%d") if date_created else timezone.now().strftime("%Y-%m-%d")
    carpeta = f"compra{compra_id}-{fecha_hora}"
    tipo = "factura" if tipo_comprobante == "01" else "boleta"
    filename = f"compra-{tipo}-{fecha}-{kind}{ext.lower()}"
    return f"{base}/{tienda}/{carpeta}/{filename}"


def _r2_public_url(key):
    if getattr(settings, "R2_PUBLIC_URL", None):
        return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
    return f"{settings.R2_ENDPOINT_URL.rstrip('/')}/{settings.R2_BUCKET_NAME}/{key}"


def _subir_archivo_compra(file_obj, *, tienda, comprobante, kind, allowed_exts):
    """Sube un archivo de compra a R2 y devuelve su URL pública."""
    from botocore.exceptions import ClientError

    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in allowed_exts:
        raise ValueError(f"El archivo {kind} debe tener extensión {', '.join(allowed_exts)}")

    key = build_compra_r2_key(
        debug=settings.DEBUG,
        tienda_nombre=getattr(tienda, "nombre", None),
        compra_id=comprobante.id,
        date_created=comprobante.date_created,
        tipo_comprobante=comprobante.tipo_comprobante,
        kind=kind,
        ext=ext,
    )
    try:
        _r2_client().upload_fileobj(
            file_obj, settings.R2_BUCKET_NAME, key,
            ExtraArgs={"ContentType": R2_CONTENT_TYPES.get(ext, "application/octet-stream")},
        )
    except ClientError as e:
        logger.error("Error subiendo %s de compra %s a R2: %s", kind, comprobante.id, e)
        raise RuntimeError(f"Error al subir {kind} a Cloudflare R2: {e}")
    return _r2_public_url(key)


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


def _borrar_r2_por_url(url):
    """Borra un objeto R2 a partir de su URL (best-effort: nunca rompe el flujo)."""
    key = _r2_key_desde_url(url)
    if not key:
        return
    try:
        _r2_client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    except Exception as e:
        logger.warning("No se pudo borrar objeto R2 %s: %s", key, e)


def _es_truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "si", "sí", "yes", "y")


def _get_archivo_request(request, kind):
    aliases, _ = ARCHIVOS_COMPRA[kind]
    for alias in aliases:
        f = request.FILES.get(alias)
        if f:
            return f
    return None


def _validar_extension_archivo(file_obj, kind):
    _, allowed = ARCHIVOS_COMPRA[kind]
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in allowed:
        raise ValueError(f"El archivo {kind} debe tener extensión {', '.join(allowed)}")


def _parse_json_field(value, default):
    """Acepta dict/list o string JSON (viene como string con multipart/form-data)."""
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return default


def _comprobante_to_json(c):
    return {
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
        # URLs unificadas (null si fue formulario manual sin archivos)
        "xml_url": c.xml_url,
        "pdf_url": c.pdf_url,
        "image_url": c.image_url,
        # Legacy (registros antiguos con FileField)
        "archivo_xml": c.archivo_xml.url if getattr(c, "archivo_xml", None) and c.archivo_xml else None,
        "archivo_pdf": c.archivo_pdf.url if getattr(c, "archivo_pdf", None) and c.archivo_pdf else None,
        "items": c.items,
        "observaciones": c.observaciones,
        "date_created": c.date_created.isoformat() if c.date_created else None,
    }


class CrearCompraView(APIView):
    """ÚNICO endpoint de creación.

    Soporta los 2 modos del frontend con el mismo contrato:
    1. Manual (JSON): tipo_comprobante, serie, correlativo, fecha_emision, items + opcionales.
    2. Con archivos (multipart/form-data): mismos campos + files `xml` / `pdf` / `imagen`
       (también acepta URLs directas `xml_url` / `pdf_url` / `image_url`).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        try:
            data = request.data
            tienda = request.user.tienda

            # ============ OBLIGATORIOS (se mantienen) ============
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

            items = _parse_json_field(data.get("items", []), [])
            if not items or len(items) == 0:
                errores.append("Debe incluir al menos un item")

            if errores:
                return Response(
                    {"error": "Campos obligatorios faltantes", "detalles": errores},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ============ DUPLICADOS ============
            existe = ComprobanteCompra.objects.filter(
                tienda=tienda,
                tipo_comprobante=tipo_comprobante,
                serie=str(serie).strip().upper(),
                correlativo=str(correlativo).strip(),
            ).exists()
            if existe:
                return Response(
                    {
                        "error": "Comprobante duplicado",
                        "detalle": f"Ya existe un comprobante con tipo {tipo_comprobante}, serie {serie} y correlativo {correlativo} en esta tienda."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ============ PROVEEDOR ============
            proveedor_data = _parse_json_field(data.get("proveedor", {}), {})
            proveedor = None
            proveedor_id = proveedor_data.get("id") if isinstance(proveedor_data, dict) else None
            if proveedor_id:
                try:
                    proveedor = Proveedor.objects.get(id=proveedor_id, tienda=tienda)
                except Proveedor.DoesNotExist:
                    return Response(
                        {"error": f"Proveedor con ID {proveedor_id} no encontrado en esta tienda."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            nombre_proveedor = (proveedor_data.get("nombre") if isinstance(proveedor_data, dict) else None) or (proveedor.razon_social if proveedor else None)
            tipo_doc_proveedor = (proveedor_data.get("tipo_documento") if isinstance(proveedor_data, dict) else None) or (proveedor.ruc[:1] if proveedor and proveedor.ruc else None)
            num_doc_proveedor = (proveedor_data.get("numero_documento") if isinstance(proveedor_data, dict) else None) or (proveedor.ruc if proveedor else None)

            # ============ ARCHIVOS (R2 siempre; URLs directas opcionales) ============
            # Los files se suben DESPUÉS de crear (la carpeta incluye compra{id}).
            # Las extensiones se validan aquí para fallar con 400 sin crear huérfanos.
            archivos = {}
            for kind in ("xml", "pdf", "imagen"):
                f = _get_archivo_request(request, kind)
                if f:
                    try:
                        _validar_extension_archivo(f, kind)
                    except ValueError as e:
                        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
                    archivos[kind] = f

            xml_url = data.get("xml_url") or None
            pdf_url = data.get("pdf_url") or None
            image_url = data.get("image_url") or data.get("imagen_url") or None

            # ============ MONTOS (se mantienen) ============
            total_enviado = data.get("total")
            igv_enviado = data.get("igv")

            if total_enviado is not None and igv_enviado is not None and total_enviado != "" and igv_enviado != "":
                total = Decimal(str(total_enviado))
                igv = Decimal(str(igv_enviado))
                gravadas = total - igv
            else:
                gravadas = Decimal("0")
                for item in items:
                    cantidad = Decimal(str(item.get("cantidad", 0)))
                    precio = Decimal(str(item.get("precio_unitario", 0)))
                    descuento = Decimal(str(item.get("descuento", 0)))
                    gravadas += (cantidad * precio) - descuento
                gravadas = gravadas.quantize(Decimal("0.01"))
                igv = (gravadas * Decimal("0.18")).quantize(Decimal("0.01"))
                total = gravadas + igv

            # ============ OPCIONALES (se mantienen) ============
            moneda = data.get("moneda", "PEN") or "PEN"
            forma_pago = data.get("forma_pago", "CONTADO") or "CONTADO"
            fecha_vencimiento = data.get("fecha_vencimiento") or None
            op_exoneradas = Decimal(str(data.get("op_exoneradas", 0) or 0))
            op_inafectas = Decimal(str(data.get("op_inafectas", 0) or 0))
            op_gratuitas = Decimal(str(data.get("op_gratuitas", 0) or 0))
            dctos_totales = Decimal(str(data.get("dctos_totales", 0) or 0))
            icbper = Decimal(str(data.get("icbper", 0) or 0))
            documento_relacionado = data.get("documento_relacionado") or None
            enlace_verificacion = data.get("enlace_verificacion") or None
            observaciones = data.get("observaciones", "") or ""

            # ============ CREAR + SUBIR A R2 ============
            # 1) Se crea el registro (las URLs de archivos quedan null salvo URL directa).
            # 2) Si hay files, se suben a R2 en:
            #    BETA_COMPRAS|PRODUCCION_COMPRAS/{tienda}/compra{id}-{fecha}/compra-{factura|boleta}-{fecha}-{xml|pdf|imagen}.{ext}
            # 3) Se actualiza el registro con las URLs públicas.
            with transaction.atomic():
                comprobante = ComprobanteCompra.objects.create(
                    tienda=tienda,
                    proveedor=proveedor,
                    tipo_comprobante=tipo_comprobante,
                    serie=str(serie).strip().upper(),
                    correlativo=str(correlativo).strip(),
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
                    xml_url=xml_url,
                    pdf_url=pdf_url,
                    image_url=image_url,
                    items=items,
                    observaciones=observaciones,
                )

            if archivos:
                try:
                    actualizados = []
                    if archivos.get("xml"):
                        comprobante.xml_url = _subir_archivo_compra(
                            archivos["xml"], tienda=tienda, comprobante=comprobante,
                            kind="xml", allowed_exts=ARCHIVOS_COMPRA["xml"][1],
                        )
                        actualizados.append("xml_url")
                    if archivos.get("pdf"):
                        comprobante.pdf_url = _subir_archivo_compra(
                            archivos["pdf"], tienda=tienda, comprobante=comprobante,
                            kind="pdf", allowed_exts=ARCHIVOS_COMPRA["pdf"][1],
                        )
                        actualizados.append("pdf_url")
                    if archivos.get("imagen"):
                        comprobante.image_url = _subir_archivo_compra(
                            archivos["imagen"], tienda=tienda, comprobante=comprobante,
                            kind="imagen", allowed_exts=ARCHIVOS_COMPRA["imagen"][1],
                        )
                        actualizados.append("image_url")
                    if actualizados:
                        comprobante.save(update_fields=actualizados)
                except (ValueError, RuntimeError) as e:
                    # Sin archivos no hay compra válida: se elimina el registro huérfano.
                    comprobante.delete()
                    code = status.HTTP_400_BAD_REQUEST if isinstance(e, ValueError) else status.HTTP_500_INTERNAL_SERVER_ERROR
                    return Response({"error": str(e)}, status=code)

            return Response({
                "mensaje": "Compra registrada exitosamente",
                "comprobante": _comprobante_to_json(comprobante),
            }, status=status.HTTP_201_CREATED)

        except (ValueError, TypeError, Decimal.InvalidOperation) as e:
            return Response(
                {"error": f"Valor inválido: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            # Condición de carrera: el pre-chequeo pasó pero otro request
            # creó el mismo (tienda, tipo, serie, correlativo) primero.
            return Response(
                {
                    "error": "Comprobante duplicado",
                    "detalle": "Ya existe una compra con ese tipo, serie y correlativo en esta tienda.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error creando compra")
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ActualizarCompraView(APIView):
    """Actualiza una compra (PUT/PATCH parcial). Misma lógica que crear.

    Solo se modifican los campos enviados; lo no enviado se conserva tal cual.
    Archivos por kind (xml / pdf / imagen) — botones del frontend:
    - Reemplazar: se envía el file (`xml`/`pdf`/`imagen` + aliases) -> se sube
      a R2, se actualiza la URL y se borra el objeto anterior (best-effort).
    - Restaurar original: no se envía nada de ese kind -> se conserva la URL actual.
    - Quitar: `eliminar_xml` / `eliminar_pdf` / `eliminar_imagen` en true, o el
      campo `xml_url` / `pdf_url` / `image_url` presente pero vacío/null ->
      la URL queda en null (vacío) y se borra el objeto anterior.
      Si no tenía archivo, queda vacío (null).
    - URL directa: `xml_url` / `pdf_url` / `image_url` con valor -> se guarda tal cual.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _actualizar(self, request, id):
        try:
            data = request.data
            tienda = request.user.tienda
            comprobante = get_object_or_404(ComprobanteCompra, id=id, tienda=tienda)

            errores = []

            # ============ IDENTIFICACIÓN (solo si se envían) ============
            ntipo = comprobante.tipo_comprobante
            if "tipo_comprobante" in data:
                ntipo = data.get("tipo_comprobante")
                if not ntipo:
                    errores.append("tipo_comprobante no puede estar vacío")
                elif ntipo not in ["01", "03"]:
                    errores.append("tipo_comprobante debe ser '01' (Factura) o '03' (Boleta)")

            nserie = comprobante.serie
            if "serie" in data:
                nserie = data.get("serie")
                if not nserie or not str(nserie).strip():
                    errores.append("serie no puede estar vacía")
                else:
                    nserie = str(nserie).strip().upper()

            ncorr = comprobante.correlativo
            if "correlativo" in data:
                ncorr = data.get("correlativo")
                if not ncorr or not str(ncorr).strip():
                    errores.append("correlativo no puede estar vacío")
                else:
                    ncorr = str(ncorr).strip()

            nfecha = comprobante.fecha_emision
            if "fecha_emision" in data:
                nfecha = data.get("fecha_emision")
                if not nfecha:
                    errores.append("fecha_emision no puede estar vacía")

            # ============ ITEMS (solo si se envían) ============
            items_changed = False
            items = comprobante.items
            if "items" in data:
                items = _parse_json_field(data.get("items", []), [])
                if not items or len(items) == 0:
                    errores.append("Debe incluir al menos un item")
                else:
                    items_changed = True

            if errores:
                return Response(
                    {"error": "Campos inválidos", "detalles": errores},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ============ DUPLICADOS (excluyendo la propia compra) ============
            if (ntipo, nserie, ncorr) != (comprobante.tipo_comprobante, comprobante.serie, comprobante.correlativo):
                existe = ComprobanteCompra.objects.filter(
                    tienda=tienda,
                    tipo_comprobante=ntipo,
                    serie=nserie,
                    correlativo=ncorr,
                ).exclude(id=comprobante.id).exists()
                if existe:
                    return Response(
                        {
                            "error": "Comprobante duplicado",
                            "detalle": f"Ya existe otra compra con tipo {ntipo}, serie {nserie} y correlativo {ncorr} en esta tienda."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # ============ PROVEEDOR (solo si se envía) ============
            proveedor = comprobante.proveedor
            nombre_proveedor = comprobante.nombre_proveedor
            tipo_doc_proveedor = comprobante.tipo_documento_proveedor
            num_doc_proveedor = comprobante.numero_documento_proveedor
            if "proveedor" in data:
                proveedor_data = _parse_json_field(data.get("proveedor"), None)
                if not proveedor_data:
                    proveedor = None
                    nombre_proveedor = tipo_doc_proveedor = num_doc_proveedor = None
                elif isinstance(proveedor_data, dict):
                    proveedor = None
                    proveedor_id = proveedor_data.get("id")
                    if proveedor_id:
                        try:
                            proveedor = Proveedor.objects.get(id=proveedor_id, tienda=tienda)
                        except Proveedor.DoesNotExist:
                            return Response(
                                {"error": f"Proveedor con ID {proveedor_id} no encontrado en esta tienda."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                    nombre_proveedor = proveedor_data.get("nombre") or (proveedor.razon_social if proveedor else None)
                    tipo_doc_proveedor = proveedor_data.get("tipo_documento") or (proveedor.ruc[:1] if proveedor and proveedor.ruc else None)
                    num_doc_proveedor = proveedor_data.get("numero_documento") or (proveedor.ruc if proveedor else None)
                else:
                    return Response(
                        {"error": "proveedor debe ser un objeto {id} o {nombre, tipo_documento, numero_documento}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # ============ ARCHIVOS: validar extensiones primero (400 sin cambios) ============
            archivos = {}
            for kind in ("xml", "pdf", "imagen"):
                f = _get_archivo_request(request, kind)
                if f:
                    try:
                        _validar_extension_archivo(f, kind)
                    except ValueError as e:
                        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
                    archivos[kind] = f

            # ============ MONTOS ============
            tiene_total = "total" in data and data.get("total") not in (None, "")
            tiene_igv = "igv" in data and data.get("igv") not in (None, "")
            if tiene_total != tiene_igv:
                return Response(
                    {"error": "Envíe total e igv juntos, o ninguno (se calculan desde los items)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            gravadas, igv, total = comprobante.gravadas, comprobante.igv, comprobante.total
            if tiene_total and tiene_igv:
                total = Decimal(str(data.get("total")))
                igv = Decimal(str(data.get("igv")))
                gravadas = total - igv
            elif items_changed:
                gravadas = Decimal("0")
                for item in items:
                    cantidad = Decimal(str(item.get("cantidad", 0)))
                    precio = Decimal(str(item.get("precio_unitario", 0)))
                    descuento = Decimal(str(item.get("descuento", 0)))
                    gravadas += (cantidad * precio) - descuento
                gravadas = gravadas.quantize(Decimal("0.01"))
                igv = (gravadas * Decimal("0.18")).quantize(Decimal("0.01"))
                total = gravadas + igv

            # ============ SUBIR REEMPLAZOS A R2 (antes del cambio en BD) ============
            cambios_url = {}
            borrar_urls = []
            kinds = (
                ("xml", "xml_url", ("xml_url",)),
                ("pdf", "pdf_url", ("pdf_url",)),
                ("imagen", "image_url", ("image_url", "imagen_url")),
            )
            try:
                for kind, field, url_keys in kinds:
                    actual = getattr(comprobante, field)
                    f = archivos.get(kind)
                    if f:
                        # Reemplazar
                        cambios_url[field] = _subir_archivo_compra(
                            f, tienda=tienda, comprobante=comprobante,
                            kind=kind, allowed_exts=ARCHIVOS_COMPRA[kind][1],
                        )
                        if actual:
                            borrar_urls.append(actual)
                    elif _es_truthy(data.get(f"eliminar_{kind}")):
                        # Quitar
                        cambios_url[field] = None
                        if actual:
                            borrar_urls.append(actual)
                    else:
                        for uk in url_keys:
                            if uk in data:
                                v = data.get(uk)
                                # Valor -> URL directa; vacío/null -> quitar (vacío)
                                cambios_url[field] = v or None
                                if not v and actual:
                                    borrar_urls.append(actual)
                                break
                        # Ausente -> restaurar original (conservar, no se toca)
            except RuntimeError as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # ============ OPCIONALES (solo si se envían) ============
            def _opt_str(key, actual, a_none_si_vacio=True):
                if key not in data:
                    return actual
                v = data.get(key)
                if (v is None or v == "") and a_none_si_vacio:
                    return None
                return v

            moneda = data.get("moneda") or comprobante.moneda if "moneda" in data else comprobante.moneda
            forma_pago = data.get("forma_pago") or comprobante.forma_pago if "forma_pago" in data else comprobante.forma_pago

            def _opt_decimal(key, actual):
                if key not in data or data.get(key) in (None, ""):
                    return actual
                return Decimal(str(data.get(key)))

            # ============ GUARDAR ============
            with transaction.atomic():
                comprobante.tipo_comprobante = ntipo
                comprobante.serie = nserie
                comprobante.correlativo = ncorr
                comprobante.fecha_emision = nfecha
                comprobante.fecha_vencimiento = _opt_str("fecha_vencimiento", comprobante.fecha_vencimiento)
                comprobante.forma_pago = forma_pago
                comprobante.moneda = moneda
                comprobante.gravadas = gravadas
                comprobante.op_exoneradas = _opt_decimal("op_exoneradas", comprobante.op_exoneradas)
                comprobante.op_inafectas = _opt_decimal("op_inafectas", comprobante.op_inafectas)
                comprobante.op_gratuitas = _opt_decimal("op_gratuitas", comprobante.op_gratuitas)
                comprobante.dctos_totales = _opt_decimal("dctos_totales", comprobante.dctos_totales)
                comprobante.icbper = _opt_decimal("icbper", comprobante.icbper)
                comprobante.igv = igv
                comprobante.total = total
                comprobante.proveedor = proveedor
                comprobante.tipo_documento_proveedor = tipo_doc_proveedor
                comprobante.numero_documento_proveedor = num_doc_proveedor
                comprobante.nombre_proveedor = nombre_proveedor
                comprobante.documento_relacionado = _opt_str("documento_relacionado", comprobante.documento_relacionado)
                comprobante.enlace_verificacion = _opt_str("enlace_verificacion", comprobante.enlace_verificacion)
                for field, nuevo in cambios_url.items():
                    setattr(comprobante, field, nuevo)
                comprobante.items = items
                comprobante.observaciones = _opt_str("observaciones", comprobante.observaciones, a_none_si_vacio=False)
                comprobante.save()

            for url in borrar_urls:
                _borrar_r2_por_url(url)

            return Response({
                "mensaje": "Compra actualizada exitosamente",
                "comprobante": _comprobante_to_json(comprobante),
            }, status=status.HTTP_200_OK)

        except (ValueError, TypeError, Decimal.InvalidOperation) as e:
            return Response(
                {"error": f"Valor inválido: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            return Response(
                {
                    "error": "Comprobante duplicado",
                    "detalle": "Ya existe una compra con ese tipo, serie y correlativo en esta tienda.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error actualizando compra")
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, id):
        return self._actualizar(request, id)

    def patch(self, request, id):
        return self._actualizar(request, id)


def _val_str(filtros, *keys):
    """Primer valor no vacío de las keys dadas, strip. None si no hay."""
    for k in keys:
        v = filtros.get(k)
        if v is None:
            continue
        v = str(v).strip()
        if v:
            return v
    return None


def _val_bool(filtros, *keys):
    for k in keys:
        v = filtros.get(k)
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("true", "1", "si", "sí", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
    return None


def _aplicar_filtros_compras(qs, f):
    """Aplica TODOS los filtros posibles de ComprobanteCompra. `f` dict plano."""
    # --- Búsqueda general multi-palabra (igual que antes) ---
    nombre = _val_str(f, "nombre", "search", "q")
    if nombre:
        nombre_normalizado = re.sub(r"\s+", " ", nombre.lower()).strip()
        for palabra in nombre_normalizado.split(" "):
            qs = qs.filter(
                Q(serie__icontains=palabra) |
                Q(correlativo__icontains=palabra) |
                Q(nombre_proveedor__icontains=palabra) |
                Q(numero_documento_proveedor__icontains=palabra) |
                Q(observaciones__icontains=palabra) |
                Q(documento_relacionado__icontains=palabra)
            )

    # --- Identificación ---
    tipo_comprobante = _val_str(f, "tipo_comprobante")
    if tipo_comprobante:
        qs = qs.filter(tipo_comprobante__iexact=tipo_comprobante)

    serie = _val_str(f, "serie")
    if serie:
        qs = qs.filter(serie__icontains=serie)

    correlativo = _val_str(f, "correlativo")
    if correlativo:
        qs = qs.filter(correlativo__icontains=correlativo)

    # numero_comprobante: "F001-123" | "F001" | "123" (igual que ventas)
    numero_comprobante = _val_str(f, "numero_comprobante")
    if numero_comprobante:
        limpio = numero_comprobante.replace(" ", "")
        if "-" in limpio:
            serie_part, corr_part = limpio.split("-", 1)
            if serie_part:
                qs = qs.filter(serie__iexact=serie_part)
            if corr_part:
                qs = qs.filter(correlativo__icontains=corr_part)
        else:
            qs = qs.filter(Q(serie__icontains=limpio) | Q(correlativo__icontains=limpio))

    # --- Pago / moneda ---
    forma_pago = _val_str(f, "forma_pago", "metodo_pago")
    if forma_pago:
        qs = qs.filter(forma_pago__iexact=forma_pago)

    moneda = _val_str(f, "moneda")
    if moneda:
        qs = qs.filter(moneda__iexact=moneda)

    # --- Proveedor ---
    proveedor_id = _val_str(f, "proveedor_id")
    if proveedor_id:
        try:
            qs = qs.filter(proveedor_id=int(proveedor_id))
        except (ValueError, TypeError):
            pass

    nombre_proveedor = _val_str(f, "nombre_proveedor", "proveedor", "nombre_cliente")
    if nombre_proveedor:
        qs = qs.filter(nombre_proveedor__icontains=nombre_proveedor)

    num_doc = _val_str(f, "numero_documento_proveedor", "numero_documento", "numero_documento_cliente", "ruc")
    if num_doc:
        qs = qs.filter(numero_documento_proveedor__icontains=num_doc)

    tipo_doc = _val_str(f, "tipo_documento_proveedor", "tipo_documento")
    if tipo_doc:
        qs = qs.filter(tipo_documento_proveedor__iexact=tipo_doc)

    # --- Textos ---
    observaciones = _val_str(f, "observaciones")
    if observaciones:
        qs = qs.filter(observaciones__icontains=observaciones)

    documento_relacionado = _val_str(f, "documento_relacionado")
    if documento_relacionado:
        qs = qs.filter(documento_relacionado__icontains=documento_relacionado)

    # --- Archivos: true=solo con archivo, false=solo sin archivo ---
    con_xml = _val_bool(f, "con_xml", "tiene_xml")
    if con_xml is True:
        qs = qs.filter(Q(xml_url__isnull=False) & ~Q(xml_url="") | Q(archivo_xml__isnull=False) & ~Q(archivo_xml=""))
    elif con_xml is False:
        qs = qs.filter(Q(xml_url__isnull=True) | Q(xml_url=""))

    con_pdf = _val_bool(f, "con_pdf", "tiene_pdf")
    if con_pdf is True:
        qs = qs.filter(Q(pdf_url__isnull=False) & ~Q(pdf_url="") | Q(archivo_pdf__isnull=False) & ~Q(archivo_pdf=""))
    elif con_pdf is False:
        qs = qs.filter(Q(pdf_url__isnull=True) | Q(pdf_url=""))

    con_imagen = _val_bool(f, "con_imagen", "con_foto", "tiene_imagen")
    if con_imagen is True:
        qs = qs.filter(Q(image_url__isnull=False) & ~Q(image_url=""))
    elif con_imagen is False:
        qs = qs.filter(Q(image_url__isnull=True) | Q(image_url=""))

    # --- Rangos de fecha (fecha_emision). Acepta fecha_desde/hasta y from_date/to_date (ventas) ---
    fecha_desde = _val_str(f, "fecha_desde", "from_date", "fecha_emision_desde")
    if fecha_desde:
        try:
            qs = qs.filter(fecha_emision__gte=fecha_desde)
        except (ValueError, TypeError):
            pass

    fecha_hasta = _val_str(f, "fecha_hasta", "to_date", "fecha_emision_hasta")
    if fecha_hasta:
        try:
            qs = qs.filter(fecha_emision__lte=fecha_hasta)
        except (ValueError, TypeError):
            pass

    # --- Rangos de monto ---
    total_min = _val_str(f, "total_min")
    if total_min:
        try:
            qs = qs.filter(total__gte=float(total_min))
        except (ValueError, TypeError):
            pass

    total_max = _val_str(f, "total_max")
    if total_max:
        try:
            qs = qs.filter(total__lte=float(total_max))
        except (ValueError, TypeError):
            pass

    # --- Orden ---
    order_by = _val_str(f, "order_by", "ordering") or "-date_created"
    permitidos = {
        "-date_created", "date_created",
        "-fecha_emision", "fecha_emision",
        "-total", "total",
        "-id", "id",
    }
    if order_by not in permitidos:
        order_by = "-date_created"
    qs = qs.order_by(order_by)

    return qs


def _get_paginacion(request, body):
    """Lee page/page_size/infinity_scroll desde body (POST estilo ventas) o query_params (GET).

    Igual que ventas: page_size default 5, page default 1.
    """
    qp = request.query_params

    def _int(value, default):
        try:
            v = int(value)
            return v if v >= 1 else default
        except (ValueError, TypeError):
            return default

    page = body.get("page", qp.get("page", 1)) if isinstance(body, dict) else qp.get("page", 1)
    page_size = body.get("page_size", qp.get("page_size", 5)) if isinstance(body, dict) else qp.get("page_size", 5)
    page = _int(page, 1)
    page_size = _int(page_size, 5)
    if page_size > 100:
        page_size = 100

    raw_inf = body.get("infinity_scroll", qp.get("infinity_scroll", False)) if isinstance(body, dict) else qp.get("infinity_scroll", False)
    if isinstance(raw_inf, bool):
        infinity_scroll = raw_inf
    else:
        infinity_scroll = str(raw_inf).strip().lower() in ("true", "1", "si", "sí", "yes")

    return page, page_size, infinity_scroll


def _respuesta_paginada_ventas_style(qs, page, page_size, infinity_scroll):
    """Paginación manual con el MISMO formato que ventas (SalesTotalsView).

    - Normal: {count, next, previous, index_page (0-based), length_pages, results, search_found}
    - infinity_scroll: {count, has_more, next_cursor, results}
    """
    total = qs.count()
    total_pages = ceil(total / page_size) if total else 0

    if total == 0:
        if infinity_scroll:
            return {"count": 0, "has_more": False, "next_cursor": None, "results": []}
        return {
            "count": 0, "next": None, "previous": None,
            "index_page": 0, "length_pages": 0,
            "results": [], "search_found": "not_found",
        }

    if page > total_pages:
        page = total_pages
    inicio = (page - 1) * page_size
    fin = inicio + page_size
    items = list(qs[inicio:fin])
    results = [_comprobante_to_json(c) for c in items]

    next_page = page + 1 if page < total_pages else None
    previous_page = page - 1 if page > 1 else None

    if infinity_scroll:
        return {
            "count": total,
            "has_more": next_page is not None,
            "next_cursor": next_page,
            "results": results,
        }

    return {
        "count": total,
        "next": next_page,
        "previous": previous_page,
        "index_page": page - 1,  # 0-based, igual que ventas
        "length_pages": total_pages,
        "results": results,
        "search_found": "found",
    }


class ListaComprasView(APIView):
    """Devolver compras con paginación y filtros estilo ventas.

    GET  /api/compras/lista/?page=1&page_size=5&tipo_comprobante=01&...
    POST /api/compras/lista/  body estilo ventas:
    {
      "page": 1, "page_size": 5, "infinity_scroll": false,
      "from_date": "2026-09-01", "to_date": "2026-09-30",
      "query": { "tipo_comprobante": "01", "forma_pago": "CONTADO", ... }
    }
    Filtros soportados: nombre/search/q, tipo_comprobante, serie, correlativo,
    numero_comprobante (F001-123), forma_pago/metodo_pago, moneda, proveedor_id,
    nombre_proveedor/proveedor, numero_documento_proveedor/ruc, tipo_documento_proveedor,
    observaciones, documento_relacionado, con_xml, con_pdf, con_imagen,
    fecha_desde/from_date, fecha_hasta/to_date, total_min, total_max, order_by.
    """
    permission_classes = [IsAuthenticated]

    def _listar(self, request):
        tienda = request.user.tienda
        if tienda is None:
            return Response(
                {"error": "El usuario no tiene una tienda asignada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        body = request.data if isinstance(request.data, dict) else {}
        filtros = body.get("query")
        if not isinstance(filtros, dict):
            filtros = {}

        # Unir query_params + body.query + from/to del body (estilo ventas)
        merged = dict(request.query_params)
        for k, v in filtros.items():
            if k not in merged or merged[k] in (None, ""):
                merged[k] = v
        if isinstance(body, dict):
            for alias in ("from_date", "to_date", "fecha_desde", "fecha_hasta"):
                if body.get(alias) and not merged.get(alias):
                    merged[alias] = body.get(alias)
            for alias in ("page", "page_size", "infinity_scroll"):
                if body.get(alias) is not None and not request.query_params.get(alias):
                    merged[alias] = body.get(alias)

        page, page_size, infinity_scroll = _get_paginacion(request, merged)

        qs = ComprobanteCompra.objects.filter(tienda=tienda)
        qs = _aplicar_filtros_compras(qs, merged)

        return Response(
            _respuesta_paginada_ventas_style(qs, page, page_size, infinity_scroll),
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        try:
            return self._listar(request)
        except Exception as e:
            logger.exception("Error listando compras")
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            return self._listar(request)
        except Exception as e:
            logger.exception("Error buscando compras")
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Aliases de compatibilidad (las rutas viejas siguen funcionando)
# ---------------------------------------------------------------------------
CrearComprobanteCompraView = CrearCompraView
ListaComprobantesCompraView = ListaComprasView
ActualizarComprobanteCompraView = ActualizarCompraView
