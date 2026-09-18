from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction

from core.permissions import IsSuperUser, IsAdminTienda
from .models import Tienda, PlanSuscripcion, UsoMensualTienda
from .serializers import TiendaSerializer, PlanSuscripcionSerializer
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated

User = get_user_model()



# ============================================
# SUPERUSER: Gestionar tiendas
# ============================================

class GetAllTiendas(APIView):
    """Superuser + AdminTienda: ver tiendas (superuser ve todas, admin ve la suya + sucursales)"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            tiendas = Tienda.objects.all()
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
            tiendas = Tienda.objects.filter(is_deleted=False).filter(
                Q(id=user.tienda.id) | Q(tienda_padre=user.tienda) | Q(propietario=user)  # type: ignore
            ).distinct()
        serializer = TiendaSerializer(tiendas, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateTienda(APIView):
    """Superuser + AdminTienda: crear tienda/sucursal"""
    permission_classes = [IsAuthenticated, IsAdminTienda]
    parser_classes = [MultiPartParser, FormParser]

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
        if nombre_tienda and Tienda.objects.filter(nombre__iexact=nombre_tienda).exists():
            return Response(
                {"error": f"Ya existe una tienda con el nombre '{nombre_tienda}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        # Si es admin_tienda y no es superuser, forzar que la tienda creada quede vinculada a ÃƒÂ©l
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
                if not data.get("propietario"):
                    data["propietario"] = user.id  # type: ignore
            # Admin no puede elegir otro propietario ni serie libremente (se respeta UpdateTienda restriction, pero aquÃƒÂ­ tambiÃƒÂ©n)
            # Permitir serie, pero serÃƒÂ¡ validada por serializer

        serializer = TiendaSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            tienda = serializer.save()
            # Sucursal: el propietario debe ser el mismo de la tienda padre
            if tienda.tienda_padre and tienda.propietario != tienda.tienda_padre.propietario:
                tienda.propietario = tienda.tienda_padre.propietario
                tienda.save(update_fields=["propietario"])
                serializer = TiendaSerializer(tienda, context={"request": request})
            # Asegurar propietario para admin que crea tienda principal sin propietario explÃƒÂ­cito
            elif not user.is_superuser and tienda.propietario is None and tienda.tienda_padre is None:
                tienda.propietario = user  # type: ignore
                tienda.save(update_fields=["propietario"])
                serializer = TiendaSerializer(tienda, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# SUPERUSER + ADMIN TIENDA: Ver tienda
# ============================================

class GetTienda(APIView):
    """Ver una tienda por ID"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request, id):
        tienda = get_object_or_404(Tienda, id=id, is_deleted=False)
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

        if not request.user.is_superuser:
            campos_restringidos = ['serie', 'propietario', 'tienda_padre']
            for campo in campos_restringidos:
                data.pop(campo, None)

        serializer = TiendaSerializer(tienda, data=data, partial=True, context={"request": request})
        if serializer.is_valid():
            if 'logo_img' in request.FILES and tienda.logo_img:
                tienda.logo_img.delete(save=False)
            serializer.save()

            # Propagar campos de empresa a tiendas hijas (sucursales)
            campos_empresa = ['ruc', 'razon_social', 'sol_password', 'cert_clave_publica']
            campos_editados = [c for c in campos_empresa if c in data]

            if campos_editados:
                sucursales = Tienda.objects.filter(tienda_padre=tienda)
                for sucursal in sucursales:
                    for campo in campos_editados:
                        setattr(sucursal, campo, data.get(campo))
                    sucursal.save(update_fields=campos_editados)

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeactivateTienda(APIView):
    """Activar/desactivar tienda"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def patch(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)

        activo = request.data.get('activo', None)
        if activo is None:
            return Response(
                {"error": "'activo' es requerido (true o false)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        tienda.activo = activo
        tienda.save()

        User.objects.filter(tienda=tienda).update(is_active=activo)

        mensaje = "Tienda activada correctamente" if activo else "Tienda desactivada correctamente"
        return Response({"message": mensaje, "tienda_id": tienda.id, "activo": tienda.activo}, status=status.HTTP_200_OK)


class HabilitarTiendaEliminada(APIView):
    """Habilitar tienda eliminada"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def put(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)
        tienda.is_deleted = False
        tienda.save()
        User.objects.filter(tienda=tienda).update(is_active=True)
        return Response(
            {"message": "Tienda habilitada y usuarios reactivados correctamente."},
            status=status.HTTP_200_OK
        )


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
            tiendas = Tienda.objects.filter(is_deleted=False)
            return Response(TiendaSerializer(tiendas, many=True, context={"request": request}).data, status=status.HTTP_200_OK)

        if not user.tienda:
            return Response(
                {"error": "No tienes tienda asociada"},
                status=status.HTTP_404_NOT_FOUND
            )

        sucursales = Tienda.objects.filter(
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

        # Obtener uso mensual actual
        from datetime import date
        hoy = date.today()
        mes_actual = hoy.replace(day=1)
        uso_actual = UsoMensualTienda.objects.filter(tienda=tienda, mes=mes_actual).first()

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
                "precio_mensual": str(plan_actual.precio_mensual),
                "precio_anual": str(plan_actual.precio_anual),
                "moneda": plan_actual.moneda,
                "periodo_facturacion": plan_actual.periodo_facturacion,
                "activo": plan_actual.activo,
            }

        uso_mensual_data = None
        if uso_actual:
            uso_mensual_data = {
                "boletas_emitidas": uso_actual.boletas_emitidas,
                "facturas_emitidas": uso_actual.facturas_emitidas,
                "mes": uso_actual.mes.iso_format(),
            }

        response_data = {
            "plan_actual": plan_actual_data,
            "uso_mensual": uso_mensual_data,
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

        # Asignar el nuevo plan a la tienda
        tienda.plan = nuevo_plan
        tienda.save()

        # Retornar la info actualizada de la tienda con su nuevo plan
        from .serializers import TiendaSerializer, PlanSuscripcionSerializer
        serializer = TiendaSerializer(tienda, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


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
