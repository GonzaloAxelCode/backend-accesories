from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
import json

from core.permissions import IsSuperUser, IsAdminTienda
from .models import Tienda, PlanSuscripcion, UsoMensualTienda
from .serializers import TiendaSerializer, PlanSuscripcionSerializer
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated

User = get_user_model()


# Datos de empresa/SUNAT que la sucursal hereda de su tienda padre
# (al crearla y cada vez que se actualiza el padre): RUC, razón social,
# certificados SUNAT, credenciales Clave SOL y claves GRE.
CAMPOS_HEREDADOS_SUCURSAL = [
    'ruc', 'razon_social',
    'certificado', 'cert_clave_publica', 'cert_clave_privada',
    'sol_user', 'sol_password',
    'client_id', 'client_secret',
]


def heredar_datos_padre(sucursal, padre=None):
    """Copia los datos de empresa/SUNAT del padre a la sucursal."""
    padre = padre or sucursal.tienda_padre
    if padre is None:
        return sucursal
    for campo in CAMPOS_HEREDADOS_SUCURSAL:
        setattr(sucursal, campo, getattr(padre, campo))
    sucursal.save(update_fields=CAMPOS_HEREDADOS_SUCURSAL)
    return sucursal


def _normalizar_propietario_write(data):
    """Mueve el legacy `propietario: <id>` a `propietario_id` (campo de
    escritura). Si `propietario` es dict lo deja intacto (lo gestiona
    CreateTienda como creación de usuario)."""
    if "propietario_id" in data:
        return
    prop = data.get("propietario")
    if prop is None or isinstance(prop, dict):
        return
    data.pop("propietario", None)
    data["propietario_id"] = prop



# ============================================
# SUPERUSER: Gestionar tiendas
# ============================================

class GetAllTiendas(APIView):
    """Superuser + AdminTienda: ver tiendas (superuser ve todas, admin ve la suya + sucursales)"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            tiendas = Tienda.objects.prefetch_related("sucursales").all()
        else:
            # Solo admin_tienda puede listar: verificar que sea propietario
            is_admin = user.tienda and user.tienda.propietario_id == user.id  # type: ignore
            if not is_admin:
                return Response(
                    {"detail": "Solo superuser o admin_tienda puede listar tiendas."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Admin ve su tienda principal + sus sucursales + tiendas donde es propietario
            from django.db.models import Q
            tiendas = Tienda.objects.prefetch_related("sucursales").filter(is_deleted=False).filter(
                Q(id=user.tienda.id) | Q(tienda_padre=user.tienda) | Q(propietario=user)  # type: ignore
            ).distinct()
        serializer = TiendaSerializer(tiendas, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateTienda(APIView):
    """Superuser + AdminTienda: crear tienda/sucursal.

    `propietario` acepta:
    - id (int) → propietario existente (solo superuser, como antes).
    - objeto {username, password, [first_name, last_name]} → crea el
      usuario admin_tienda de la nueva tienda (username exacto, sensible
      a mayúsculas). Solo superuser y solo tiendas principales (no
      sucursales). Por form-data llega como string JSON.
    """
    permission_classes = [IsAuthenticated, IsAdminTienda]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request):
        user = request.user
        # Validar que sea superuser o admin_tienda
        is_admin = user.is_superuser or (user.tienda and user.tienda.propietario_id == user.id)  # type: ignore
        if not is_admin:
            return Response(
                {"detail": "Solo superuser o admin_tienda puede crear tiendas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        nombre_tienda = request.data.get("nombre")
        if isinstance(nombre_tienda, str):
            nombre_tienda = nombre_tienda.strip()
        if nombre_tienda and Tienda.objects.filter(nombre__iexact=nombre_tienda).exists():
            return Response(
                {"error": f"Ya existe una tienda o sucursal con el nombre '{nombre_tienda}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()

        # Normalizar `propietario`: dict (JSON) o string JSON (form-data).
        # Un int/str numérico es un propietario existente (flujo anterior,
        # normalizado a `propietario_id` más abajo).
        propietario_data = None
        propietario_raw = data.get("propietario")
        if isinstance(propietario_raw, dict):
            propietario_data = propietario_raw
        elif isinstance(propietario_raw, str) and propietario_raw.strip().startswith("{"):
            try:
                propietario_data = json.loads(propietario_raw)
            except (ValueError, TypeError):
                return Response(
                    {"error": "El objeto 'propietario' no es un JSON válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not isinstance(propietario_data, dict):
                return Response(
                    {"error": "El objeto 'propietario' debe ser {username, password}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if propietario_data is not None:
            # Solo superuser puede crear tienda con propietario nuevo y
            # solo para tiendas principales (la sucursal hereda el
            # propietario del padre, ver abajo).
            if not user.is_superuser:
                return Response(
                    {"error": "Solo superuser puede crear una tienda con un propietario nuevo."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if data.get("tienda_padre"):
                return Response(
                    {"error": "No envíes 'propietario' al crear una sucursal: hereda el propietario de la tienda padre."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            nuevo_username = propietario_data.get("username")
            nuevo_password = propietario_data.get("password")
            if not isinstance(nuevo_username, str) or not nuevo_username:
                return Response(
                    {"error": "propietario.username es requerido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not isinstance(nuevo_password, str) or not nuevo_password:
                return Response(
                    {"error": "propietario.password es requerido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if User.objects.filter(username=nuevo_username).exists():
                return Response(
                    {"error": f"Ya existe un usuario con el username '{nuevo_username}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Retirar del payload: el usuario se crea después de la tienda.
            data.pop("propietario", None)

        # Compatibilidad escritura: `propietario: <id>` → `propietario_id`.
        _normalizar_propietario_write(data)

        # Si es admin_tienda y no es superuser, forzar que la tienda creada quede vinculada a Ã©l
        # - Si crea sucursal (tienda_padre), debe ser su propia tienda
        # - Si crea tienda principal, asignarle como propietario si no viene
        if not user.is_superuser:
            # Sucursal: forzar tienda_padre a su tienda principal si lo intenta crear
            tienda_padre_id = data.get("tienda_padre")
            if tienda_padre_id:
                # Validar que el padre sea su tienda
                if str(tienda_padre_id) != str(user.tienda.id):  # type: ignore
                    return Response(
                        {"error": "Solo puedes crear sucursales de tu propia tienda."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                # Tienda principal: auto-asignar propietario si no viene
                if not data.get("propietario_id"):
                    data["propietario_id"] = user.id  # type: ignore
            # Admin no puede elegir otro propietario ni serie libremente (se respeta UpdateTienda restriction, pero aquÃ­ tambiÃ©n)
            # Permitir serie, pero serÃ¡ validada por serializer

        serializer = TiendaSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        tienda = serializer.save()

        # Crear el usuario admin_tienda de la nueva tienda.
        propietario_creado = None
        if propietario_data is not None:
            propietario_creado = User.objects.create_user(
                username=propietario_data["username"],
                password=propietario_data["password"],
                first_name=propietario_data.get("first_name", ""),
                last_name=propietario_data.get("last_name", ""),
                tienda=tienda,
            )
            tienda.propietario = propietario_creado
            tienda.save(update_fields=["propietario"])

        # Sucursal: el propietario debe ser el mismo de la tienda padre
        # y hereda sus datos de empresa/SUNAT (el padre siempre manda).
        if tienda.tienda_padre:
            if tienda.propietario != tienda.tienda_padre.propietario:
                tienda.propietario = tienda.tienda_padre.propietario
                tienda.save(update_fields=["propietario"])
            heredar_datos_padre(tienda)
        # Asegurar propietario para admin que crea tienda principal sin propietario explÃ­cito
        elif not user.is_superuser and tienda.propietario is None and tienda.tienda_padre is None:
            tienda.propietario = user  # type: ignore
            tienda.save(update_fields=["propietario"])

        # Plan Demo por defecto si la tienda no trae plan (no toca planes pago).
        if tienda.plan_id is None:
            from django.utils import timezone
            from .models import PlanSuscripcion
            from .seeders import PLAN_DEMO_NOMBRE, seed_planes
            try:
                demo = PlanSuscripcion.objects.get(nombre_plan=PLAN_DEMO_NOMBRE)
            except PlanSuscripcion.DoesNotExist:
                seed_planes()
                demo = PlanSuscripcion.objects.get(nombre_plan=PLAN_DEMO_NOMBRE)
            tienda.plan = demo
            if not tienda.plan_desde:
                tienda.plan_desde = timezone.now()
            tienda.save(update_fields=["plan", "plan_desde"])

        response_data = TiendaSerializer(tienda, context={"request": request}).data
        if propietario_creado is not None:
            response_data["propietario_creado"] = {
                "id": propietario_creado.id,  # type: ignore
                "username": propietario_creado.username,
                "first_name": propietario_creado.first_name,
                "last_name": propietario_creado.last_name,
            }
        return Response(response_data, status=status.HTTP_201_CREATED)


# ============================================
# SUPERUSER + ADMIN TIENDA: Ver tienda
# ============================================

class GetTienda(APIView):
    """Ver una tienda por ID"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request, id):
        tienda = get_object_or_404(
            Tienda.objects.prefetch_related("sucursales"), id=id, is_deleted=False
        )
        self.check_object_permissions(request, tienda)
        serializer = TiendaSerializer(tienda, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateTienda(APIView):
    """Actualizar tienda"""
    permission_classes = [IsAuthenticated, IsAdminTienda]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)

        data = request.data.copy()

        # Compatibilidad escritura: `propietario: <id>` → `propietario_id`.
        _normalizar_propietario_write(data)

        if not request.user.is_superuser:
            campos_restringidos = ['serie', 'propietario', 'propietario_id', 'tienda_padre']
            for campo in campos_restringidos:
                data.pop(campo, None)

        serializer = TiendaSerializer(tienda, data=data, partial=True, context={"request": request})
        if serializer.is_valid():
            if 'logo_img' in request.FILES and tienda.logo_img:
                tienda.logo_img.delete(save=False)
            serializer.save()

            # Propagar datos de empresa/SUNAT a las sucursales (mismo set
            # que heredan al crearse): RUC, razón social, certificados,
            # Clave SOL y claves GRE.
            campos_editados = [c for c in CAMPOS_HEREDADOS_SUCURSAL if c in data]

            if campos_editados:
                sucursales = Tienda.objects.filter(tienda_padre=tienda)
                for sucursal in sucursales:
                    for campo in campos_editados:
                        setattr(sucursal, campo, data.get(campo))
                    sucursal.save(update_fields=campos_editados)

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateTiendaLogos(APIView):
    """Actualizar solo los logos de la tienda (logo, logo dark, banner)"""
    permission_classes = [IsAuthenticated, IsAdminTienda]
    parser_classes = [MultiPartParser, FormParser]

    CAMPOS = ("logo_img", "logo_img_dark", "banner_img")

    def patch(self, request, id):
        tienda = get_object_or_404(Tienda, id=id, is_deleted=False)
        self.check_object_permissions(request, tienda)

        recibidos = [c for c in self.CAMPOS if c in request.FILES]
        if not recibidos:
            return Response(
                {"error": "Envía al menos una imagen: logo_img, logo_img_dark o banner_img."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Solo se aceptan los 3 campos de imagen (nada más se toca)
        data = {campo: request.FILES[campo] for campo in recibidos}
        serializer = TiendaSerializer(tienda, data=data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Borrar archivos anteriores para no acumular huérfanos en media/
        for campo in recibidos:
            anterior = getattr(tienda, campo)
            if anterior:
                anterior.delete(save=False)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


def _parse_bool(value):
    """Convierte true/false (bool, int, str) a bool. Retorna None si no es válido."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "t", "yes", "y", "si", "sí"):
            return True
        if v in ("false", "0", "f", "no", "n"):
            return False
    return None


class EliminarTemporalTienda(APIView):
    """Borrado temporal: marca la tienda como is_deleted=True (activo=False)
    y desactiva todo su personal (users is_active=False)."""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def _eliminar(self, request, id):
        tienda = get_object_or_404(Tienda, id=id, is_deleted=False)
        self.check_object_permissions(request, tienda)

        # Liberar nombre/RUC originales (unique): se concatenan con el
        # sufijo "_is_deleted_{id}". Con truncado si exceden el max_length.
        sufijo = f"_is_deleted_{tienda.id}"
        max_nombre = Tienda._meta.get_field("nombre").max_length
        nuevo_nombre = f"{tienda.nombre}{sufijo}"
        if len(nuevo_nombre) > max_nombre:
            nuevo_nombre = f"{tienda.nombre[:max_nombre - len(sufijo)]}{sufijo}"
        tienda.nombre = nuevo_nombre
        if tienda.ruc:
            max_ruc = Tienda._meta.get_field("ruc").max_length
            nuevo_ruc = f"{tienda.ruc}{sufijo}"
            if len(nuevo_ruc) > max_ruc:
                nuevo_ruc = f"{tienda.ruc[:max_ruc - len(sufijo)]}{sufijo}"
            tienda.ruc = nuevo_ruc

        tienda.is_deleted = True
        # save() fuerza activo=False cuando is_deleted=True
        tienda.save()

        User.objects.filter(tienda=tienda).update(is_active=False)

        return Response(
            {
                "message": "Tienda eliminada temporalmente y usuarios desactivados correctamente.",
                "tienda_id": tienda.id,
                "nombre": tienda.nombre,
                "is_deleted": tienda.is_deleted,
                "activo": tienda.activo,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, id):
        return self._eliminar(request, id)

    def delete(self, request, id):
        return self._eliminar(request, id)

    def post(self, request, id):
        return self._eliminar(request, id)


class RestaurarTiendaEliminada(APIView):
    """Restaura una tienda eliminada temporalmente: is_deleted=False,
    activo=True. Los usuarios se dejan como están (desactivados)."""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def _restaurar(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)

        if not tienda.is_deleted:
            return Response(
                {"error": "La tienda no está eliminada temporalmente."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Revertir el sufijo "_is_deleted_{id}" para recuperar nombre/RUC
        # originales. Si otra tienda activa ya tomó ese nombre, no se restaura.
        sufijo = f"_is_deleted_{tienda.id}"
        nombre_orig = tienda.nombre[:-len(sufijo)] if tienda.nombre.endswith(sufijo) else tienda.nombre
        if Tienda.objects.filter(nombre__iexact=nombre_orig, is_deleted=False).exclude(id=tienda.id).exists():
            return Response(
                {"error": f"No se puede restaurar: el nombre '{nombre_orig}' ya está en uso por otra tienda."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tienda.nombre = nombre_orig
        if tienda.ruc and tienda.ruc.endswith(sufijo):
            tienda.ruc = tienda.ruc[:-len(sufijo)] or None

        tienda.is_deleted = False
        tienda.activo = True
        tienda.save()

        # Intencional: NO reactivar usuarios, quedan desactivados.
        return Response(
            {
                "message": "Tienda restaurada correctamente. Los usuarios permanecen desactivados.",
                "tienda_id": tienda.id,
                "nombre": tienda.nombre,
                "is_deleted": tienda.is_deleted,
                "activo": tienda.activo,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        return self._restaurar(request, id)

    def patch(self, request, id):
        return self._restaurar(request, id)

    def post(self, request, id):
        return self._restaurar(request, id)


class ToggleActivacionTienda(APIView):
    """Activa/desactiva tienda sin borrarla.

    POST {"activate": true|false} (se acepta alias "activo"/"is_active"):
    - activate=false: activo=False + desactiva sus usuarios.
    - activate=true: activo=True, usuarios se dejan como están.
    """
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def _toggle(self, request, id):
        tienda = get_object_or_404(Tienda, id=id, is_deleted=False)
        self.check_object_permissions(request, tienda)

        raw = request.data.get(
            "activate",
            request.data.get("activo", request.data.get("is_active", None)),
        )
        if raw is None:
            return Response(
                {"error": "'activate' es requerido (true o false)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activar = _parse_bool(raw)
        if activar is None:
            return Response(
                {"error": "'activate' debe ser true o false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tienda.activo = activar
        tienda.save(update_fields=["activo"])

        if not activar:
            User.objects.filter(tienda=tienda).update(is_active=False)
            mensaje = "Tienda desactivada correctamente y usuarios desactivados."
        else:
            # Intencional: al reactivar, los usuarios se dejan como están.
            mensaje = "Tienda activada correctamente. Los usuarios se dejan como están."

        return Response(
            {"message": mensaje, "tienda_id": tienda.id, "activo": tienda.activo},
            status=status.HTTP_200_OK,
        )

    def post(self, request, id):
        return self._toggle(request, id)

    def patch(self, request, id):
        return self._toggle(request, id)


# Aliases retrocompatibles (las rutas antiguas fueron renombradas)
DeactivateTienda = EliminarTemporalTienda
HabilitarTiendaEliminada = RestaurarTiendaEliminada


# ============================================
# ADMIN TIENDA: Ver mi tienda
# ============================================

class UpdateTiendaStyles(APIView):
    """Actualizar estilos de tienda (boleta ticket, boleta pdf, factura pdf)"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def patch(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)

        tipo_style_boleta_ticket = request.data.get('tipo_style_boleta_ticket')
        tipo_style_boleta_pdf = request.data.get('tipo_style_boleta_pdf')
        tipo_style_factura_pdf = request.data.get('tipo_style_factura_pdf')

        if all(v in (None, '') for v in (tipo_style_boleta_ticket, tipo_style_boleta_pdf, tipo_style_factura_pdf)):
            return Response(
                {"error": "Debes enviar 'tipo_style_boleta_ticket', 'tipo_style_boleta_pdf' o 'tipo_style_factura_pdf'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        for nombre, valor in (
            ('tipo_style_boleta_ticket', tipo_style_boleta_ticket),
            ('tipo_style_boleta_pdf', tipo_style_boleta_pdf),
            ('tipo_style_factura_pdf', tipo_style_factura_pdf),
        ):
            if valor in (None, ''):
                continue
            if not isinstance(valor, str) or len(valor) > 100:
                return Response(
                    {"error": f"'{nombre}' debe ser string de mÃƒÂ¡ximo 100 caracteres."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            setattr(tienda, nombre, valor)

        tienda.save()

        serializer = TiendaSerializer(tienda, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class GetMiTiendaView(APIView):
    """Admin tienda: ver mi tienda"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            tiendas = Tienda.objects.prefetch_related("sucursales").filter(is_deleted=False)
            return Response(TiendaSerializer(tiendas, many=True, context={"request": request}).data, status=status.HTTP_200_OK)

        if not user.tienda:
            return Response(
                {"error": "No tienes tienda asociada"},
                status=status.HTTP_404_NOT_FOUND
            )

        sucursales = Tienda.objects.prefetch_related("sucursales").filter(
            tienda_padre=user.tienda, is_deleted=False
        )
        return Response(
            TiendaSerializer(sucursales, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK
        )


class GetPlanosYSuscripcionTienda(APIView):
    """Ver plan actual y estado de uso de una tienda"""
    permission_classes = [IsAuthenticated]

    def get(self, request, tienda_id):
        tienda = get_object_or_404(Tienda, id=tienda_id, is_deleted=False)

        # Verificar permisos: solo superuser o admin de la tienda
        user = request.user
        if user.is_superuser:
            pass
        elif user.tienda and user.tienda.id == tienda.id:
            pass
        else:
            return Response(
                {"error": "No tienes permisos para ver esta informaciÃ³n."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Obtener plan actual de la tienda (solo uno)
        plan_actual = tienda.plan

        # Renovación automática si el periodo venció (guarda historial y
        # reinicia el contador), luego uso vs. límites del periodo vigente.
        from .utils import get_estado_limites, renovar_si_vencido
        renovacion = renovar_si_vencido(tienda)
        uso = get_estado_limites(tienda)

        # Preparar datos
        plan_actual_data = None
        if plan_actual:
            plan_actual_data = {
                "id": plan_actual.id,
                "nombre_plan": plan_actual.nombre_plan,
                "descripcion": plan_actual.descripcion,
                "lista_descripcion": plan_actual.lista_descripcion or [],
                "limite_boletas": plan_actual.limite_boletas,
                "limite_facturas": plan_actual.limite_facturas,
                "limite_personal": plan_actual.limite_personal,
                "limite_productos": plan_actual.limite_productos,
                "precio_mensual": str(plan_actual.precio_mensual),
                "precio_anual": str(plan_actual.precio_anual),
                "moneda": plan_actual.moneda,
                "periodo_facturacion": plan_actual.periodo_facturacion,
                "activo": plan_actual.activo,
            }

        uso_mensual_data = {
            "boletas_emitidas": uso["boletas_emitidas"],
            "facturas_emitidas": uso["facturas_emitidas"],
            "periodo_inicio": uso["inicio"].isoformat(),
            "periodo_fin": uso["fin"].isoformat(),
            "periodo_vencido": uso["vencido"],
            "dias_restantes": uso["dias_restantes"],
        }

        historial = [
            {
                "inicio": h.inicio.isoformat(),
                "fin": h.fin.isoformat(),
                "plan_id": h.plan_id,
                "boletas_emitidas": h.boletas_emitidas,
                "facturas_emitidas": h.facturas_emitidas,
                "fecha_registro": h.fecha_registro.isoformat(),
            }
            for h in tienda.historial_periodos.all()[:6]
        ]

        response_data = {
            "plan_actual": plan_actual_data,
            "plan_desde": tienda.plan_desde.isoformat() if tienda.plan_desde else None,
            "periodo_inicio": uso["inicio"].isoformat(),
            "periodo_fin": uso["fin"].isoformat(),
            "uso_mensual": uso_mensual_data,
            "estado_limites": {
                "sin_plan": uso["sin_plan"],
                "num_personal": uso["num_personal"],
                "num_productos": uso["num_productos"],
                "limite_productos": uso["limite_productos"],
                "excede_boletas": uso["excede_boletas"],
                "excede_facturas": uso["excede_facturas"],
                "excede_personal": uso["excede_personal"],
                "excede_productos": uso["excede_productos"],
                "bloqueado_productos": uso["bloqueado_productos"],
            },
            "periodo_renovado": renovacion["renovado"],
            "periodos_saltados": renovacion["periodos_saltados"],
            "historial_periodos": historial,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class CreatePlanSuscripcion(APIView):
    """Superuser: crear un nuevo plan de suscripciÃ³n"""
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        serializer = PlanSuscripcionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ListPlanSuscripcion(APIView):
    """Listar todos los planes disponibles (para selector/assign)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        planes = PlanSuscripcion.objects.all().order_by('precio_mensual')
        serializer = PlanSuscripcionSerializer(planes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePlanTienda(APIView):
    """Superuser o admin_tienda: cambiar el plan de una tienda"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, tienda_id):
        tienda = get_object_or_404(Tienda, id=tienda_id, is_deleted=False)

        # Verificar permisos
        user = request.user
        if user.is_superuser:
            pass
        elif user.tienda and user.tienda.id == tienda.id:
            pass
        else:
            return Response(
                {"error": "No tienes permisos para cambiar el plan de esta tienda."},
                status=status.HTTP_403_FORBIDDEN
            )

        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response(
                {"error": "El campo 'plan_id' es requerido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            nuevo_plan = PlanSuscripcion.objects.get(id=plan_id)
        except PlanSuscripcion.DoesNotExist:
            return Response(
                {"error": "El plan especificado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )

        from datetime import date
        from django.utils import timezone
        from .utils import get_uso_periodo

        # Uso previo (conteo en vivo) antes del reset, para auditoría
        uso_previo = get_uso_periodo(tienda)
        plan_anterior_id = tienda.plan_id

        # Asignar el nuevo plan e iniciar un periodo de 30 días desde ahora.
        # Sin bloqueo de emisiones y sin prorrateo: el contador parte de 0.
        tienda.plan = nuevo_plan
        tienda.plan_desde = timezone.now()
        tienda.save(update_fields=["plan", "plan_desde"])

        # Reset de compatibilidad: UsoMensualTienda ya no es fuente de verdad
        # (el conteo es en vivo), pero se deja en 0 para no mostrar saldos viejos.
        mes_actual = date.today().replace(day=1)
        UsoMensualTienda.objects.update_or_create(
            tienda=tienda,
            mes=mes_actual,
            defaults={"boletas_emitidas": 0, "facturas_emitidas": 0},
        )

        uso_nuevo = get_uso_periodo(tienda)

        # Retornar la info actualizada de la tienda con su nuevo plan
        from .serializers import TiendaSerializer, PlanSuscripcionSerializer
        serializer = TiendaSerializer(tienda, context={"request": request})
        data = serializer.data
        data["cambio_plan"] = {
            "plan_anterior_id": plan_anterior_id,
            "plan_nuevo_id": nuevo_plan.id,
            "plan_desde": tienda.plan_desde.isoformat(),
            "uso_previo": {
                "boletas_emitidas": uso_previo["boletas_emitidas"],
                "facturas_emitidas": uso_previo["facturas_emitidas"],
            },
            "uso_reseteado": {
                "boletas_emitidas": uso_nuevo["boletas_emitidas"],
                "facturas_emitidas": uso_nuevo["facturas_emitidas"],
                "periodo_inicio": uso_nuevo["inicio"].isoformat(),
                "periodo_fin": uso_nuevo["fin"].isoformat(),
            },
        }
        return Response(data, status=status.HTTP_200_OK)


class UpdatePlanSuscripcion(APIView):
    """Superuser: actualizar cualquier campo de un plan existente"""
    permission_classes = [IsAuthenticated, IsSuperUser]

    def patch(self, request, plan_id):
        plan = get_object_or_404(PlanSuscripcion, id=plan_id)
        serializer = PlanSuscripcionSerializer(plan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, plan_id):
        plan = get_object_or_404(PlanSuscripcion, id=plan_id)
        serializer = PlanSuscripcionSerializer(plan, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeletePlanSuscripcion(APIView):
    """Superuser: eliminar un plan de suscripción.

    Las tiendas que tenían ese plan pasan a plan=null (ilimitado:
    sin plan no hay bloqueos, ver get_estado_limites con sin_plan=True).
    """
    permission_classes = [IsAuthenticated, IsSuperUser]

    def _eliminar(self, request, plan_id):
        plan = get_object_or_404(PlanSuscripcion, id=plan_id)

        with transaction.atomic():
            # Tienda.plan es PROTECT, por eso primero se desvincula.
            liberadas = Tienda.objects.filter(plan=plan).update(plan=None, plan_desde=None)
            plan_nombre = plan.nombre_plan
            plan.delete()

        return Response(
            {
                "message": f"Plan '{plan_nombre}' eliminado correctamente.",
                "plan_id": plan_id,
                "tiendas_liberadas": liberadas,
                "detalle": "Las tiendas afectadas quedaron con plan=null (ilimitado, sin bloqueos).",
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, plan_id):
        return self._eliminar(request, plan_id)

    def post(self, request, plan_id):
        return self._eliminar(request, plan_id)
