from rest_framework import serializers
from .models import Repuesto


class RepuestoSerializer(serializers.ModelSerializer):
    tienda_nombre = serializers.SerializerMethodField()
    categoria_nombre = serializers.SerializerMethodField()
    proveedor_nombre = serializers.SerializerMethodField()
    # Alias de compatibilidad: el frontend histórico usa "cantidad", el modelo usa "stock"
    cantidad = serializers.IntegerField(source="stock", read_only=True)
    # Declarado explícito para exigirlo (el modelo tiene default="" solo por filas legacy)
    nombre = serializers.CharField(max_length=200, required=True, allow_blank=False, trim_whitespace=True)
    # Obligatorios: el default del modelo es solo para filas legacy, el API los exige
    stock = serializers.IntegerField(required=True, min_value=0)
    valorizacion = serializers.DecimalField(max_digits=10, decimal_places=2, required=True, min_value=0)

    class Meta:
        model = Repuesto
        fields = [
            "id", "tienda", "tienda_nombre",
            "categoria", "categoria_nombre",
            "proveedor", "proveedor_nombre",
            "nombre", "modelos_compatibles", "ubicacion",
            "stock", "cantidad", "valorizacion",
            "imagen1", "imagen2",
            "activo", "is_deleted",
            "date_created", "fecha_actualizacion",
        ]
        read_only_fields = ["id", "tienda", "date_created", "fecha_actualizacion"]

    def validate_nombre(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("El nombre del repuesto es obligatorio.")
        return value.strip()

    def validate(self, attrs):
        tienda = attrs.get("tienda") or getattr(self.instance, "tienda", None)
        if tienda is None and self.context.get("request") is not None:
            tienda = getattr(self.context["request"].user, "tienda", None)
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", None) if self.instance else None)
        if isinstance(nombre, str):
            nombre = nombre.strip()
        if tienda and nombre:
            qs = Repuesto.objects.filter(tienda=tienda, nombre__iexact=nombre, activo=True, is_deleted=False)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"nombre": "Ya existe un repuesto con ese nombre en tu tienda."})
        return attrs

    def get_tienda_nombre(self, obj):
        return obj.tienda.nombre if obj.tienda else None

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else None

    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if obj.proveedor else None
