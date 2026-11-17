from django.db.models import Q
from rest_framework import serializers
from .models import Celular


class CelularSerializer(serializers.ModelSerializer):
    tienda_nombre = serializers.SerializerMethodField()
    # Todos obligatorios en create (los defaults del modelo son solo para filas legacy)
    estado_equipo = serializers.ChoiceField(choices=Celular.ESTADO_EQUIPO_CHOICES)
    costo_compra = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    precio_venta = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    dualSim = serializers.BooleanField()
    disponible = serializers.BooleanField()

    class Meta:
        model = Celular
        fields = [
            "id", "tienda", "tienda_nombre",
            "marca", "modelo", "color", "memoria", "ram",
            "estado_equipo", "imei1", "imei2",
            "dualSim",
            "costo_compra", "precio_venta",
            "disponible",
            "imagen1", "imagen2",
            "activo", "is_deleted",
            "date_created", "fecha_actualizacion",
        ]
        read_only_fields = ["id", "tienda", "date_created", "fecha_actualizacion"]
        extra_kwargs = {
            "ram": {"required": True},
            "imei2": {"required": True, "allow_blank": False},
            "imagen1": {"required": True},
            "imagen2": {"required": True},
        }

    def get_tienda_nombre(self, obj):
        return obj.tienda.nombre if obj.tienda else None

    def validate_imei1(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("El IMEI 1 es obligatorio.")
        return value

    def validate_imei2(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("El IMEI 2 es obligatorio.")
        return value

    def validate(self, attrs):
        # En update parcial, usar valores de instancia para validar duplicados.
        # En create, tienda viene por save(tienda=...) no por attrs -> sacarla del request.
        tienda = attrs.get("tienda") or getattr(self.instance, "tienda", None)
        if tienda is None and self.context.get("request") is not None:
            tienda = getattr(self.context["request"].user, "tienda", None)
        imei1 = attrs.get("imei1", getattr(self.instance, "imei1", None) if self.instance else None)
        if isinstance(imei1, str):
            imei1 = imei1.strip()
        imei2 = attrs.get("imei2", getattr(self.instance, "imei2", None) if self.instance else None)
        if isinstance(imei2, str):
            imei2 = imei2.strip()
        # Blindaje cruzado: ninguno de los dos IMEI puede coincidir con
        # el imei1 o imei2 de otro equipo activo de la tienda.
        nuevos = {v for v in (imei1, imei2) if v}
        if tienda and nuevos:
            qs = Celular.objects.filter(tienda=tienda, activo=True, is_deleted=False).filter(
                Q(imei1__in=nuevos) | Q(imei2__in=nuevos)
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"imei1": "Ese IMEI ya está registrado en otro equipo de tu tienda."})
        return attrs
