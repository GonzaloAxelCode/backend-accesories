import traceback

import requests
from datetime import datetime
from math import ceil
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.settings import SUNAT_API_KEY, SUNAT_PHP

from apps.tienda.models import Tienda

from .models import GuiaRemision
from .serializers import GuiaRemisionListSerializer, GuiaRemisionSerializer


def resolve_tienda(request, tienda_id=None):
    """Resuelve la tienda: la que mande el frontend (`tienda: id`) o la del usuario.

    Si el frontend manda un id distinto al del usuario, se valida acceso:
    superuser/staff, propietario de la tienda o sucursal de su tienda.
    Retorna (tienda, error_response).
    """
    propia = getattr(request.user, "tienda", None)
    if not tienda_id:
        if not propia:
            return None, Response(
                {"error": "El usuario no tiene una tienda asignada"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return propia, None
    # Puede llegar como id (query/body) o como instancia (validated_data del serializer).
    if isinstance(tienda_id, Tienda):
        tienda = tienda_id
    else:
        try:
            tienda = Tienda.objects.select_related("tienda_padre").get(pk=tienda_id)
        except (Tienda.DoesNotExist, ValueError, TypeError):
            return None, Response(
                {"error": f"Tienda {tienda_id} no existe"},
                status=status.HTTP_404_NOT_FOUND,
            )
    user = request.user
    permitido = (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or (propia and tienda.pk == propia.pk)
        or tienda.propietario_id == getattr(user, "pk", None)
        or (propia and tienda.tienda_padre_id == propia.pk)
    )
    if not permitido:
        return None, Response(
            {"error": "No tienes acceso a esta tienda"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return tienda, None


def siguiente_correlativo(tienda, serie):
    ultimo = (
        GuiaRemision.objects.filter(tienda=tienda, serie=serie)
        .order_by("-correlativo")
        .first()
    )
    if ultimo and ultimo.correlativo.isdigit():
        return str(int(ultimo.correlativo) + 1).zfill(8)
    # Sin guías previas en la serie: parte del correlativo inicial de la tienda.
    inicial = getattr(tienda, "correlativo_inicial_guia_remision", None) or 1
    return str(inicial).zfill(8)


def _log_guia(msg):
    # print directo para garantizar que salga en la consola del runserver.
    print(f"[GUIA] {msg}", flush=True)


def _post_a_sunat(payload, serie, correlativo):
    """POST al endpoint PHP de guías. Retorna (data_php, error).

    - Si hay excepción de red/timeout: imprime trace en consola y error es 502.
    - Si el PHP devuelve no-JSON o status != 200 o {success:false} / {error}:
      imprime cuerpo en consola y error es 502/400 con el detalle.
    - Si todo ok: error es None.
    """
    url = f"{SUNAT_PHP.rstrip('/')}/src/api/guia-remision-post.php"
    _log_guia(f"SEND {serie}-{correlativo} -> {url}")
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "X-API-Key": SUNAT_API_KEY},
            timeout=30,
        )
    except Exception as e:
        _log_guia(f"EXCEPTION send {serie}-{correlativo}: {e}")
        traceback.print_exc()
        return None, Response(
            {"error": "No se pudo contactar al servicio SUNAT/PHP", "detalle": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    try:
        data_php = resp.json()
    except ValueError:
        _log_guia(
            f"NON-JSON {serie}-{correlativo}: HTTP {resp.status_code} "
            f"body={resp.text[:2000]}"
        )
        return None, Response(
            {"error": "El PHP no devolvió JSON válido", "detalle": resp.text[:2000]},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if resp.status_code != 200 or data_php.get("error") or data_php.get("success") is False:
        _log_guia(
            f"REJECT {serie}-{correlativo}: HTTP {resp.status_code} detalle={data_php}"
        )
        return None, Response(
            {"error": "SUNAT/PHP rechazó la guía", "detalle": data_php},
            status=status.HTTP_400_BAD_REQUEST,
        )

    _log_guia(
        f"OK {serie}-{correlativo}: guia={data_php.get('guia')} "
        f"ambiente={data_php.get('ambiente')}"
    )
    return data_php, None


class GuiaRemisionPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class GuiaRemisionViewSet(viewsets.ModelViewSet):
    serializer_class = GuiaRemisionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = GuiaRemisionPagination

    def get_queryset(self):
        qs = GuiaRemision.objects.all().prefetch_related(
            "items", "docs_relacionados", "conductores"
        )
        p = self.request.query_params
        # ?tienda=1 permite listar otra tienda con acceso (si no, la del usuario)
        tienda, error = resolve_tienda(self.request, p.get("tienda"))
        if error is not None:
            return qs.none()
        qs = qs.filter(tienda=tienda)
        # Filtros rápidos por query params en el GET del router:
        # ?serie=T001&estado=ACEPTADO&mod_traslado=02&search=1020&from_date=2026-09-01&to_date=2026-09-30
        if p.get("serie"):
            qs = qs.filter(serie__iexact=p["serie"].strip())
        if p.get("estado"):
            qs = qs.filter(estado__iexact=p["estado"].strip())
        if p.get("estado_sunat"):
            qs = qs.filter(estado_sunat__icontains=p["estado_sunat"].strip())
        if p.get("mod_traslado"):
            qs = qs.filter(mod_traslado=p["mod_traslado"].strip())
        if p.get("search"):
            s = p["search"].strip()
            qs = qs.filter(
                Q(numero_guia__icontains=s)
                | Q(correlativo__icontains=s)
                | Q(dest_num_doc__icontains=s)
                | Q(dest_nombre__icontains=s)
                | Q(vehiculo_placa__icontains=s)
            )
        if p.get("from_date") and p.get("to_date"):
            try:
                tz = ZoneInfo("America/Lima")
                desde = datetime.strptime(p["from_date"], "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, tzinfo=tz
                )
                hasta = datetime.strptime(p["to_date"], "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=tz
                )
                qs = qs.filter(fecha_emision__range=(desde, hasta))
            except (ValueError, TypeError):
                pass
        return qs

    def perform_create(self, serializer):
        # `tienda` puede venir del frontend; si no, se usa la del usuario.
        tienda, error = resolve_tienda(
            self.request, serializer.validated_data.get("tienda")
        )
        if error is not None:
            from rest_framework.exceptions import PermissionDenied, ValidationError
            raise (
                PermissionDenied(error.data)
                if error.status_code == status.HTTP_403_FORBIDDEN
                else ValidationError(error.data)
            )
        serie = serializer.validated_data.get("serie", "T001")
        correlativo = serializer.validated_data.get("correlativo")
        if not correlativo:
            correlativo = siguiente_correlativo(tienda, serie)
        serializer.save(
            tienda=tienda,
            usuario=self.request.user,
            serie=serie,
            correlativo=correlativo,
        )


class BuscarGuiasRemisionView(APIView):
    """Listado con filtros + rango de fechas (mismo estilo que sales/search/).

    POST api/guias-remision/search/
    {
      "tienda": 1,                 // opcional: id de tienda (si no, la del usuario)
      "from_date": "2026-09-01",   // YYYY-MM-DD (opcional)
      "to_date": "2026-09-30",     // YYYY-MM-DD (opcional)
      "page": 1,
      "page_size": 10,
      "query": {
        "serie": "T001",
        "numero_guia": "T001-00000001",  // busca en numero_guia o correlativo
        "estado": "ACEPTADO",            // BORRADOR|ENVIADO|ACEPTADO|RECHAZADO|ERROR
        "estado_sunat": "Aceptado",
        "mod_traslado": "02",            // 01 público | 02 privado
        "cod_traslado": "01",
        "dest_nombre": "CLIENTE",
        "dest_num_doc": "20000000001",
        "vehiculo_placa": "AAA-111"
      }
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        page_number = int(body.get("page", 1) or 1)
        page_size = int(body.get("page_size", 10) or 10)
        page_size = min(max(page_size, 1), 100)
        query = body.get("query") or {}

        # `tienda` opcional desde el frontend para filtrar otra tienda con acceso.
        tienda, error = resolve_tienda(request, body.get("tienda"))
        if error is not None:
            return error
        guias = GuiaRemision.objects.filter(tienda=tienda)

        # --- Rango de fechas sobre fecha_emision (America/Lima) ---
        from_date_str = body.get("from_date")
        to_date_str = body.get("to_date")
        if from_date_str and to_date_str:
            try:
                tz = ZoneInfo("America/Lima")
                desde = datetime.strptime(from_date_str, "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
                )
                hasta = datetime.strptime(to_date_str, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=0, tzinfo=tz
                )
                guias = guias.filter(fecha_emision__range=(desde, hasta))
            except (ValueError, TypeError):
                return Response(
                    {"error": "Formato de fecha inválido. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # --- Filtros opcionales ---
        if query.get("serie"):
            guias = guias.filter(serie__iexact=query["serie"].strip())
        if query.get("estado"):
            guias = guias.filter(estado__iexact=query["estado"].strip())
        if query.get("estado_sunat"):
            guias = guias.filter(estado_sunat__icontains=query["estado_sunat"].strip())
        if query.get("mod_traslado"):
            guias = guias.filter(mod_traslado=query["mod_traslado"].strip())
        if query.get("cod_traslado"):
            guias = guias.filter(cod_traslado=query["cod_traslado"].strip())
        if query.get("dest_nombre"):
            guias = guias.filter(dest_nombre__icontains=query["dest_nombre"].strip())
        if query.get("dest_num_doc"):
            guias = guias.filter(dest_num_doc__icontains=query["dest_num_doc"].strip())
        if query.get("vehiculo_placa"):
            guias = guias.filter(vehiculo_placa__icontains=query["vehiculo_placa"].strip())
        if query.get("numero_guia"):
            n = query["numero_guia"].strip()
            guias = guias.filter(Q(numero_guia__icontains=n) | Q(correlativo__icontains=n))

        guias = guias.annotate(num_items=Count("items")).order_by("-fecha_emision")

        total = guias.count()
        total_pages = ceil(total / page_size) if total else 1
        page_number = min(max(page_number, 1), total_pages)
        inicio = (page_number - 1) * page_size
        page_qs = guias[inicio:inicio + page_size]

        return Response({
            "count": total,
            "next": page_number + 1 if page_number < total_pages else None,
            "previous": page_number - 1 if page_number > 1 else None,
            "index_page": page_number - 1,
            "length_pages": total_pages,
            "results": GuiaRemisionListSerializer(page_qs, many=True).data,
        })


class CrearGuiaRemisionView(APIView):
    """Vista dedicada para crear una guía.

    POST api/guias-remision/crear/
    Mismo body que el serializer (ver ejemplo para el frontend).
    - Si no mandas `correlativo`, se autogenera (siguiente de la serie).
    - Si mandas `"enviar": true`, además la envía a SUNAT en la misma
      petición y devuelve xml/pdf/cdr.
    - Si el envío a SUNAT falla (500, rechazo, timeout...), se imprime el
      detalle en consola ([GUIA] ...) y NO se crea ni se guarda la guía
      (rollback total de la transacción).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = dict(request.data) if isinstance(request.data, dict) else {}
        enviar = data.pop("enviar", False)
        # La tienda es la del usuario logueado, no se pide al frontend:
        # se ignora lo que mande el body y se inyecta la del request.
        data.pop("tienda", None)
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data["tienda"] = tienda.pk
        serie = (data.get("serie") or "T001").strip()
        if not data.get("correlativo"):
            data["correlativo"] = siguiente_correlativo(tienda, serie)

        serializer = GuiaRemisionSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            guia = serializer.save(tienda=tienda, usuario=request.user)

            if not enviar:
                return Response(
                    {
                        "guia": GuiaRemisionSerializer(guia).data,
                        "correlativo_generado": guia.correlativo,
                    },
                    status=status.HTTP_201_CREATED,
                )

            payload = guia.build_payload()
            data_php, error = _post_a_sunat(payload, guia.serie, guia.correlativo)
            if error is not None:
                # Falla el envío -> rollback: la guía no se crea ni se guarda.
                _log_guia(
                    f"ROLLBACK {guia.serie}-{guia.correlativo}: "
                    "no se guarda la guia por fallo de SUNAT/PHP"
                )
                transaction.set_rollback(True)
                return error

            guia.payload_enviado = payload
            guia.aplicar_respuesta(data_php)
            return Response(
                {
                    "guia": GuiaRemisionSerializer(guia).data,
                    "correlativo_generado": guia.correlativo,
                    "envio": {
                        "ok": True,
                        "numero_guia": guia.numero_guia,
                        "ambiente": guia.ambiente,
                        "xml_url": guia.xml_url,
                        "pdf_url": guia.pdf_url,
                        "cdr_url": guia.cdr_url,
                    },
                },
                status=status.HTTP_201_CREATED,
            )


class ProximoCorrelativoGuiaView(APIView):
    """GET api/guias-remision/proximo-correlativo/?serie=T001 → {"serie","correlativo"}.

    Útil para pre-llenar el formulario del frontend antes de crear.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda, error = resolve_tienda(request, request.query_params.get("tienda"))
        if error is not None:
            return error
        serie = (request.query_params.get("serie") or "T001").strip()
        return Response({
            "tienda": tienda.pk,
            "serie": serie,
            "correlativo": siguiente_correlativo(tienda, serie),
            "fecha_emision": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


class EnviarGuiaRemisionView(APIView):
    """Toma una guía en BORRADOR, arma el payload y la envía al PHP de SUNAT.

    Si el envío falla (500, rechazo, timeout...), se imprime el detalle en
    consola ([GUIA] ...) y la guía queda intacta (no se guarda ENVIADO/ERROR).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        guia = get_object_or_404(GuiaRemision, pk=pk or request.data.get("guia_id"))
        payload = guia.build_payload()

        with transaction.atomic():
            data_php, error = _post_a_sunat(payload, guia.serie, guia.correlativo)
            if error is not None:
                # Falla el envío -> rollback: la guía queda como estaba.
                _log_guia(
                    f"ROLLBACK {guia.serie}-{guia.correlativo}: "
                    "la guia queda intacta por fallo de SUNAT/PHP"
                )
                transaction.set_rollback(True)
                return error

            # Solo se persiste si SUNAT aceptó.
            guia.payload_enviado = payload
            guia.estado = "ENVIADO"
            guia.save(update_fields=["payload_enviado", "estado"])
            guia.aplicar_respuesta(data_php)

        return Response(
            {
                "guia_id": guia.id,  # type: ignore
                "numero_guia": guia.numero_guia,
                "ambiente": guia.ambiente,
                "xml_url": guia.xml_url,
                "pdf_url": guia.pdf_url,
                "cdr_url": guia.cdr_url,
                "payload_enviado": guia.payload_enviado,
                "respuesta_php": data_php,
            },
            status=status.HTTP_200_OK,
        )
