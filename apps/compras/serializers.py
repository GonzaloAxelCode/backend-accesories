from rest_framework import serializers
from apps.compras.models import ComprobanteCompra


class ComprobanteCompraSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)
    tipo_comprobante_display = serializers.CharField(source="get_tipo_comprobante_display", read_only=True)

    class Meta:
        model = ComprobanteCompra
        fields = [
            "id",
            "tienda",
            "proveedor",
            "proveedor_nombre",
            "ruc_proveedor",
            "tipo_comprobante",
            "tipo_comprobante_display",
            "serie",
            "correlativo",
            "total",
            "xml_constancia",
            "xml_comprobante",
            "pdf_url",
            "estado_codigo",
            "estado_descripcion",
            "date_created",
        ]
        read_only_fields = ["id", "tienda", "date_created"]

    def validate_ruc_proveedor(self, value):
        if value in (None, ""):
            return value
        v = str(value).strip()
        if not v.isdigit() or len(v) != 11:
            raise serializers.ValidationError("ruc_proveedor debe tener 11 dígitos")
        return v

    def validate_serie(self, value):
        v = str(value or "").strip().upper()
        if not v:
            raise serializers.ValidationError("serie es obligatoria")
        return v

    def validate_total(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("total no puede ser negativo")
        return value

    def validate_correlativo(self, value):
        v = str(value or "").strip()
        if not v:
            raise serializers.ValidationError("correlativo es obligatorio")
        return v
