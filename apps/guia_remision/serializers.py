from django.utils import timezone
from rest_framework import serializers

from .models import (
    GuiaDocumentoRelacionado,
    GuiaRemision,
    GuiaRemisionConductor,
    GuiaRemisionItem,
)


class GuiaRemisionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuiaRemisionItem
        fields = ["id", "codigo", "descripcion", "unidad", "cantidad", "cod_prod_sunat", "atributos"]


class GuiaDocumentoRelacionadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuiaDocumentoRelacionado
        fields = ["id", "tipo_desc", "tipo", "nro", "emisor"]


# Catálogo 06 SUNAT (tipo de documento de identidad): un solo carácter.
# 0 = doc. trib. no dom. sin RUC, 1 = DNI, 4 = carnet extranjería,
# 6 = RUC, 7 = pasaporte, A = cédula diplomática. Sin cero a la izquierda.
TIPOS_DOC_IDENTIDAD_SUNAT = {"0", "1", "4", "6", "7", "A"}


def normalizar_tipo_doc(value, campo):
    """Normaliza '01'->'1', '06'->'6', etc. y valida contra el catálogo 06."""
    if value in (None, ""):
        return value
    v = str(value).strip().upper()
    if len(v) == 2 and v.startswith("0"):
        v = v[1:]
    if v not in TIPOS_DOC_IDENTIDAD_SUNAT:
        raise serializers.ValidationError({
            campo: (
                f"Tipo de documento '{value}' inválido. "
                "SUNAT catálogo 06 usa un solo carácter: "
                "0, 1 (DNI), 4, 6 (RUC), 7, A."
            )
        })
    return v


class GuiaRemisionConductorSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuiaRemisionConductor
        fields = ["id", "tipo", "tipo_doc", "nro_doc", "nombres", "apellidos", "licencia"]

    def validate(self, attrs):
        if attrs.get("tipo_doc"):
            attrs["tipo_doc"] = normalizar_tipo_doc(attrs["tipo_doc"], "tipo_doc")
        return attrs


class GuiaRemisionListSerializer(serializers.ModelSerializer):
    """Versión liviana para el listado (sin anidados, con conteos)."""

    num_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = GuiaRemision
        fields = [
            "id", "tienda", "serie", "correlativo", "numero_guia",
            "fecha_emision", "fec_traslado", "observacion",
            "dest_tipo_doc", "dest_num_doc", "dest_nombre",
            "mod_traslado", "cod_traslado", "des_traslado",
            "peso_total", "num_bultos",
            "partida_ubigeo", "partida_direccion",
            "llegada_ubigeo", "llegada_direccion",
            "vehiculo_placa",
            "estado", "estado_sunat", "ambiente",
            "xml_url", "pdf_url", "cdr_url",
            "num_items", "date_created",
        ]


class GuiaRemisionSerializer(serializers.ModelSerializer):
    items = GuiaRemisionItemSerializer(many=True)
    docs_relacionados = GuiaDocumentoRelacionadoSerializer(many=True, required=False)
    conductores = GuiaRemisionConductorSerializer(many=True)

    class Meta:
        model = GuiaRemision
        fields = [
            "id", "tienda", "usuario", "venta", "pedido",
            "serie", "correlativo", "numero_guia", "fecha_emision", "observacion",
            "emisor_ubigeo", "emisor_departamento", "emisor_provincia",
            "emisor_distrito", "emisor_direccion", "emisor_nombre_comercial",
            "dest_tipo_doc", "dest_num_doc", "dest_nombre", "dest_direccion",
            "tercero_tipo_doc", "tercero_num_doc", "tercero_nombre",
            "comprador_tipo_doc", "comprador_num_doc", "comprador_nombre",
            "mod_traslado", "cod_traslado", "des_traslado", "fec_traslado",
            "peso_total", "und_peso_total", "peso_items", "sustento_peso", "num_bultos",
            "partida_ubigeo", "partida_direccion", "partida_cod_local", "partida_ruc",
            "llegada_ubigeo", "llegada_direccion", "llegada_cod_local", "llegada_ruc",
            "transportista_tipo_doc", "transportista_num_doc",
            "transportista_nombre", "transportista_nro_mtc",
            "vehiculo_placa", "vehiculo_nro_circulacion",
            "vehiculo_nro_autorizacion", "vehiculo_cod_emisor",
            "vehiculo_secundarios", "indicadores", "contenedores", "logo_url",
            "estado", "estado_sunat", "ambiente",
            "xml_url", "pdf_url", "cdr_url",
            "payload_enviado", "respuesta_sunat",
            "items", "docs_relacionados", "conductores",
            "date_created",
        ]
        read_only_fields = [
            "numero_guia", "estado", "estado_sunat", "ambiente",
            "xml_url", "pdf_url", "cdr_url",
            "payload_enviado", "respuesta_sunat",
        ]

    def validate(self, attrs):
        # Catálogo 06: destinatario, transportista, tercero y comprador
        # usan un solo carácter ("6", "1", ...). Se normaliza "01"->"1", etc.
        # (OJO: docs_relacionados[].tipo es catálogo de comprobantes "01"/"03" y no se toca.)
        for campo in (
            "dest_tipo_doc", "transportista_tipo_doc",
            "tercero_tipo_doc", "comprador_tipo_doc",
        ):
            if attrs.get(campo):
                attrs[campo] = normalizar_tipo_doc(attrs[campo], campo)
        # SUNAT error 3343: inicio del traslado >= fecha de emisión.
        fec_traslado = attrs.get("fec_traslado")
        fecha_emision = attrs.get("fecha_emision") or timezone.now()
        if fec_traslado and fec_traslado < fecha_emision.date():
            raise serializers.ValidationError({
                "fec_traslado": (
                    f"Debe ser mayor o igual a la fecha de emisión "
                    f"({fecha_emision.date().isoformat()}). "
                    "SUNAT (error 3343) exige inicio de traslado >= fecha de emisión."
                )
            })
        # Al menos 1 ítem y 1 conductor (obligatorios en la API PHP).
        items = self.initial_data.get("items", [])
        conductores = self.initial_data.get("conductores", [])
        if not items:
            raise serializers.ValidationError({"items": "La guía debe tener al menos 1 ítem."})
        if not conductores:
            raise serializers.ValidationError(
                {"conductores": "La guía debe tener al menos 1 conductor."}
            )
        # SUNAT error 3410: codLocal y ruc van siempre juntos en cada punto.
        # Si la dirección NO es un local declarado, manda ambos vacíos.
        errores = {}
        for pref in ("partida", "llegada"):
            cod = attrs.get(f"{pref}_cod_local")
            ruc = attrs.get(f"{pref}_ruc")
            if cod and not ruc:
                errores[f"{pref}_ruc"] = (
                    f"Si mandas {pref}_cod_local debes mandar {pref}_ruc "
                    "(RUC titular del establecimiento). SUNAT error 3410."
                )
            if ruc and not cod:
                errores[f"{pref}_cod_local"] = (
                    f"Si mandas {pref}_ruc debes mandar {pref}_cod_local. "
                    "SUNAT error 3410."
                )
            if ruc and (not str(ruc).isdigit() or len(str(ruc)) != 11):
                errores[f"{pref}_ruc"] = "El RUC debe tener 11 dígitos numéricos."
        if errores:
            raise serializers.ValidationError(errores)
        # Transporte público (01) exige datos del transportista.
        if attrs.get("mod_traslado", "02") == "01":
            faltantes = [
                f for f in (
                    "transportista_tipo_doc", "transportista_num_doc",
                    "transportista_nombre", "transportista_nro_mtc",
                )
                if not attrs.get(f)
            ]
            if faltantes:
                raise serializers.ValidationError(
                    f"Transporte público (01) requiere: {', '.join(faltantes)}."
                )
        return attrs

    def create(self, validated_data):
        items = validated_data.pop("items", [])
        docs = validated_data.pop("docs_relacionados", [])
        conductores = validated_data.pop("conductores", [])
        guia = GuiaRemision.objects.create(**validated_data)
        for i in items:
            GuiaRemisionItem.objects.create(guia=guia, **i)
        for d in docs:
            GuiaDocumentoRelacionado.objects.create(guia=guia, **d)
        for c in conductores:
            GuiaRemisionConductor.objects.create(guia=guia, **c)
        return guia
