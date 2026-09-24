# apps/tienda/serializers.py
from django.db.models import Q
from rest_framework import serializers

from apps.user.models import UserAccount
from apps.user.serializers import UserSerializer
from .models import Tienda, PlanSuscripcion, UsoMensualTienda


class PropietarioDataSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = UserAccount
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "photo_url",
            "is_active",
            "es_empleado",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class PlanSuscripcionSerializer(serializers.ModelSerializer):

    class Meta:
        model = PlanSuscripcion
        fields = [
            'id', 'nombre_plan', 'descripcion', 'lista_descripcion',
            'limite_boletas',
            'limite_facturas', 'limite_personal', 'limite_productos',
            'precio_mensual',
            'precio_anual',
            'moneda', 'periodo_facturacion', 'activo', 'fecha_creacion'
        ]


class TiendaSerializer(serializers.ModelSerializer):

    users_tienda = UserSerializer(many=True, read_only=True)
    propietario_data = PropietarioDataSerializer(source="propietario", read_only=True)
    # `propietario` ahora es objeto anidado (id, username, nombres, foto...).
    # Para escribir se usa `propietario_id` (también se acepta el legacy
    # `propietario: <id>`, normalizado en las vistas).
    propietario = serializers.SerializerMethodField()
    propietario_id = serializers.PrimaryKeyRelatedField(
        queryset=UserAccount.objects.all(),
        source="propietario",
        write_only=True,
        required=False,
        allow_null=True,
    )
    # Tiendas hijas (sucursales) completas, un solo nivel: en contexto
    # anidado se devuelve [] para evitar recursión infinita.
    sucursales = serializers.SerializerMethodField()
    subscripcion_data = PlanSuscripcionSerializer(source="plan", read_only=True)
    tienda_stats = serializers.SerializerMethodField()
    # Flags de estado (el frontend muestra "configurado" sin ver el secreto)
    tiene_sol = serializers.SerializerMethodField()
    tiene_certificado = serializers.SerializerMethodField()
    tiene_credenciales_guia = serializers.SerializerMethodField()
    # Periodo vigente del plan (ventana de 30 días desde plan_desde)
    plan_hasta = serializers.SerializerMethodField()
    plan_dias_restantes = serializers.SerializerMethodField()
    plan_periodo_vencido = serializers.SerializerMethodField()

    class Meta:
        model = Tienda
        fields = '__all__'
        extra_kwargs = {
            # Secretos SUNAT: se pueden guardar/actualizar pero NUNCA se
            # devuelven en ningún GET. Ver get_tiene_* para el estado visible.
            'cert_clave_privada': {'write_only': True},
            'cert_clave_publica': {'write_only': True},
            'sol_user': {'write_only': True},
            'sol_password': {'write_only': True},
            'client_id': {'write_only': True},
            'client_secret': {'write_only': True},
            'certificado': {'write_only': True},
        }

    def get_propietario(self, obj):
        if not obj.propietario:
            return None
        return PropietarioDataSerializer(obj.propietario).data

    def get_sucursales(self, obj):
        if self.context.get("tienda_nested"):
            return []
        hijas = obj.sucursales.filter(is_deleted=False).order_by("-date_created")
        contexto = dict(self.context)
        contexto["tienda_nested"] = True
        return TiendaSerializer(hijas, many=True, context=contexto).data

    def get_tiene_sol(self, obj):
        return bool(obj.sol_user and obj.sol_password)
    def get_tiene_credenciales_guia(self, obj):
        return bool(obj.client_id and obj.client_secret)

    def get_tiene_certificado(self, obj):
        return bool(
            obj.certificado or obj.cert_clave_privada or obj.cert_clave_publica
        )

    def _periodo_plan(self, obj):
        if not obj.plan_id:
            return None, None
        from .utils import get_periodo_plan
        return get_periodo_plan(obj)

    def get_plan_hasta(self, obj):
        _, fin = self._periodo_plan(obj)
        return fin.isoformat() if fin else None

    def get_plan_dias_restantes(self, obj):
        from django.utils import timezone
        inicio, fin = self._periodo_plan(obj)
        if not fin:
            return None
        ahora = timezone.now()
        return max(0, (fin - ahora).days) if ahora < fin else 0

    def get_plan_periodo_vencido(self, obj):
        from django.utils import timezone
        _, fin = self._periodo_plan(obj)
        if not fin:
            return None
        return timezone.now() >= fin

    def validate_nombre(self, value):
        # Nombre único global (padres + sucursales), case-insensitive y
        # sin espacios laterales: "Tienda", "tienda" y " Tienda " chocan.
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre no puede estar vacío.")
        qs = Tienda.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una tienda o sucursal con este nombre.")
        return value

    def validate(self, attrs):
        # Defensa en profundidad: normalizar nombre aquí también (además de
        # validate_nombre) para que nunca se guarde con espacios laterales.
        if "nombre" in attrs and isinstance(attrs["nombre"], str):
            attrs["nombre"] = attrs["nombre"].strip()
        # Serie única dentro del grupo familiar (padre + sucursales):
        # la sucursal no puede repetir la serie del padre ni la de sus
        # hermanas, y el padre no puede tomar la de una de sus hijas.
        # Comparación case-insensitive (igual que el resto del sistema).
        # Vacías (None/"") no se validan: varias tiendas pueden no tener serie.
        if "serie" in attrs and isinstance(attrs["serie"], str):
            attrs["serie"] = attrs["serie"].strip()
        serie = attrs.get("serie", getattr(self.instance, "serie", None))
        padre = attrs.get("tienda_padre", getattr(self.instance, "tienda_padre", None))
        if serie:
            qs = Tienda.objects.filter(serie__iexact=serie)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if padre is not None:
                padre_id = padre.pk if isinstance(padre, Tienda) else padre
                if qs.filter(Q(pk=padre_id) | Q(tienda_padre_id=padre_id)).exists():
                    raise serializers.ValidationError({
                        "serie": f"La serie '{serie}' ya está en uso por la tienda padre o una sucursal hermana. Cada tienda debe tener una serie diferente."
                    })
            elif self.instance is not None:
                if qs.filter(tienda_padre=self.instance).exists():
                    raise serializers.ValidationError({
                        "serie": f"La serie '{serie}' ya está en uso por una de sus sucursales. Cada tienda debe tener una serie diferente."
                    })

        # RUC único por familia: dos tiendas padre no pueden compartir RUC.
        # Solo las sucursales pueden repetir el RUC de su propio padre
        # (lo heredan). Vacíos (None/"") no se validan.
        if "ruc" in attrs and isinstance(attrs["ruc"], str):
            attrs["ruc"] = attrs["ruc"].strip() or None
        ruc = attrs.get("ruc", getattr(self.instance, "ruc", None))
        if isinstance(ruc, str):
            ruc = ruc.strip() or None
        if ruc:
            if padre is not None:
                # Es sucursal: su RUC debe ser el de su padre (heredado).
                padre_obj = padre if isinstance(padre, Tienda) else Tienda.objects.filter(pk=padre).first()
                padre_ruc = (padre_obj.ruc or "").strip() if padre_obj else ""
                if not padre_ruc:
                    raise serializers.ValidationError({
                        "ruc": "La tienda padre no tiene RUC; la sucursal lo hereda y no puede definir uno propio."
                    })
                if ruc != padre_ruc:
                    raise serializers.ValidationError({
                        "ruc": f"La sucursal hereda el RUC de su tienda padre ({padre_ruc}) y no puede usar otro."
                    })
            else:
                # Es tienda padre/principal: el RUC no puede estar en otra familia.
                qs = Tienda.objects.filter(ruc=ruc)
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
                    # Sus propias sucursales comparten su RUC legítimamente.
                    qs = qs.exclude(tienda_padre=self.instance)
                if qs.exists():
                    raise serializers.ValidationError({
                        "ruc": f"Ya existe otra tienda con el RUC '{ruc}'. Cada tienda padre debe tener un RUC único."
                    })
        return attrs

    def get_tienda_stats(self, obj):
        from django.db.models import Count, Q, Sum

        from apps.comprobante.models import ComprobanteElectronico
        from apps.producto.models import Producto

        # Totales históricos desde comprobantes reales (no desde ventas):
        # hay ventas PENDIENTE legacy que nunca generaron comprobante e
        # inflaban los conteos. Solo boletas y facturas (case-insensitive:
        # en BD vienen como 'Boleta'/'Factura'). No cuentan RECHAZADOS ni
        # los de ventas ANULADAS. Las notas de crédito viven en otro modelo
        # y son ilimitadas: no se cuentan.
        base = (
            ComprobanteElectronico.objects.filter(
                venta__tienda=obj, venta__activo=True
            )
            .exclude(estado_sunat__iexact="RECHAZADO")
            .exclude(venta__estado__iexact="ANULADA")
        )
        stats = base.aggregate(
            boletas=Count("pk", filter=Q(tipo_comprobante__iexact="boleta")),
            facturas=Count("pk", filter=Q(tipo_comprobante__iexact="factura")),
            total=Sum(
                "total",
                filter=Q(
                    tipo_comprobante__iexact="boleta"
                ) | Q(tipo_comprobante__iexact="factura"),
            ),
        )
        boletas = stats["boletas"] or 0
        facturas = stats["facturas"] or 0
        # Productos activos de la tienda (los eliminados usan activo=False)
        num_productos = Producto.objects.filter(tienda=obj, activo=True).count()
        from .utils import get_personal_contable
        return {
            "total_comprobantes": boletas + facturas,
            "boletas": boletas,
            "facturas": facturas,
            "total_facturado": str(stats["total"] or 0),
            "num_productos": num_productos,
            "num_personal": get_personal_contable(obj).count(),
            "fecha_creacion": obj.date_created.isoformat() if obj.date_created else None,
            "nombre_suscripcion": obj.plan.nombre_plan if obj.plan else None,
        }

    def _enrich_user(self, user_data, instance, all_permissions):
        try:
            user_obj = UserAccount.objects.get(id=user_data["id"])
        except UserAccount.DoesNotExist:
            return None

        user_permissions_full = user_obj.get_all_permissions()
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]
        permissions_dict = {
            perm: perm in user_permission_codenames for perm in all_permissions
        }
        user_data["permissions"] = permissions_dict
        user_data["user_permissions_list"] = user_permission_codenames
        user_data["all_permissions_meta"] = all_permissions
        user_data["tienda_nombre"] = instance.nombre
        return user_data

    def _build_propietario_data(self, instance, all_permissions):
        propietario = instance.propietario
        if not propietario:
            return None

        propietario_serialized = PropietarioDataSerializer(propietario).data
        user_permissions_full = propietario.get_all_permissions()
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]
        propietario_serialized["permissions"] = {
            perm: perm in user_permission_codenames for perm in all_permissions
        }
        propietario_serialized["user_permissions_list"] = user_permission_codenames
        propietario_serialized["all_permissions_meta"] = all_permissions
        propietario_serialized["tienda_nombre"] = instance.nombre
        return propietario_serialized

    def to_representation(self, instance):
        data = super().to_representation(instance)

        ALL_PERMISSIONS = [
            "can_make_sale", "can_cancel_sale",
            "can_create_inventory", "can_modify_inventory",
            "can_update_inventory", "can_delete_inventory",
            "can_create_product", "can_update_product", "can_delete_product",
            "can_create_category", "can_modify_category", "can_delete_category",
            "can_create_supplier", "can_modify_supplier", "can_delete_supplier",
            "can_create_store", "can_modify_store", "can_delete_store",
            "view_sale", "view_inventory", "view_product",
            "view_category", "view_supplier", "view_store",
            "can_create_user",
            "can_create_proveedor", "can_update_proveedor", "can_delete_proveedor",
        ]

        # Defensa en profundidad: los secretos SUNAT jamás salen en un GET,
        # ni siquiera para superuser (para soporte, verlos directo en BD/admin).
        for secreto in (
            "sol_password", "sol_user",
            "cert_clave_privada", "cert_clave_publica", "certificado",
            "client_id", "client_secret",
        ):
            data.pop(secreto, None)

        enriched_users = []
        for user_data in data.get("users_tienda", []):
            enriched = self._enrich_user(user_data, instance, ALL_PERMISSIONS)
            if enriched is not None:
                enriched_users.append(enriched)

        data["users_tienda"] = enriched_users

        # Propietario enriquecido una sola vez para `propietario` y
        # `propietario_data` (compatibilidad): objeto con id, username,
        # nombres, foto + permisos.
        propietario_enriquecido = self._build_propietario_data(instance, ALL_PERMISSIONS)
        data["propietario"] = propietario_enriquecido
        data["propietario_data"] = propietario_enriquecido

        return data
