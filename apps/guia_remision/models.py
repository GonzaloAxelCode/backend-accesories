from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.tienda.models import Tienda
from core import settings

User = settings.AUTH_USER_MODEL


class GuiaRemision(models.Model):
    """Cabecera de Guía de Remisión Electrónica (GRE).

    Guarda todo lo necesario para armar el POST a
    ``src/api/guia-remision-post.php`` (header X-API-KEY + JSON)
    y persiste lo que devuelve esa API (guia, ambiente, xml/pdf/cdr urls
    + payload enviado).
    """

    MOD_TRASLADO_CHOICES = [
        ("01", "Transporte público"),
        ("02", "Transporte privado"),
    ]

    ESTADO_CHOICES = [
        ("BORRADOR", "Borrador"),
        ("ENVIADO", "Enviado"),
        ("ACEPTADO", "Aceptado"),
        ("RECHAZADO", "Rechazado"),
        ("ERROR", "Error"),
    ]

    # --- Relaciones ---
    tienda = models.ForeignKey(
        Tienda, on_delete=models.CASCADE, related_name="guias_remision"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="guias_remision",
    )
    # Opcionales: la guía puede nacer de una venta o de un pedido.
    venta = models.ForeignKey(
        "venta.Venta", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="guias_remision",
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="guias_remision",
    )

    # --- Serie / correlativo GRE ---
    # Remitente -> T001, Transportista -> V001 (ampliable).
    serie = models.CharField(max_length=4, default="T001")
    correlativo = models.CharField(max_length=8)
    # Nro. devuelto por la API, ej: "T001-00000001".
    numero_guia = models.CharField(max_length=20, null=True, blank=True)

    fecha_emision = models.DateTimeField(default=timezone.now)
    observacion = models.CharField(max_length=255, null=True, blank=True)

    # --- Snapshot emisor (lo variable; claves SOL/cert se leen de Tienda al enviar) ---
    emisor_ubigeo = models.CharField(max_length=6, null=True, blank=True)
    emisor_departamento = models.CharField(max_length=50, null=True, blank=True)
    emisor_provincia = models.CharField(max_length=50, null=True, blank=True)
    emisor_distrito = models.CharField(max_length=50, null=True, blank=True)
    emisor_direccion = models.TextField(null=True, blank=True)
    emisor_nombre_comercial = models.CharField(max_length=150, null=True, blank=True)

    # --- Destinatario (obligatorio) ---
    dest_tipo_doc = models.CharField(max_length=2, default="6")
    dest_num_doc = models.CharField(max_length=15)
    dest_nombre = models.CharField(max_length=255)
    dest_direccion = models.CharField(max_length=255, null=True, blank=True)

    # --- Tercero / comprador (opcionales) ---
    tercero_tipo_doc = models.CharField(max_length=2, null=True, blank=True)
    tercero_num_doc = models.CharField(max_length=15, null=True, blank=True)
    tercero_nombre = models.CharField(max_length=255, null=True, blank=True)

    comprador_tipo_doc = models.CharField(max_length=2, null=True, blank=True)
    comprador_num_doc = models.CharField(max_length=15, null=True, blank=True)
    comprador_nombre = models.CharField(max_length=255, null=True, blank=True)

    # --- Envío / traslado ---
    mod_traslado = models.CharField(max_length=2, choices=MOD_TRASLADO_CHOICES, default="02")
    cod_traslado = models.CharField(max_length=2, default="01")  # 01 VENTA, etc.
    des_traslado = models.CharField(max_length=100, default="VENTA")
    fec_traslado = models.DateField()

    peso_total = models.DecimalField(max_digits=12, decimal_places=3)
    und_peso_total = models.CharField(max_length=3, default="KGM")
    peso_items = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    sustento_peso = models.CharField(max_length=100, null=True, blank=True)
    num_bultos = models.PositiveIntegerField(null=True, blank=True)

    # Punto de partida
    partida_ubigeo = models.CharField(max_length=6)
    partida_direccion = models.CharField(max_length=255)
    partida_cod_local = models.CharField(max_length=10, null=True, blank=True)
    partida_ruc = models.CharField(max_length=11, null=True, blank=True)

    # Punto de llegada
    llegada_ubigeo = models.CharField(max_length=6)
    llegada_direccion = models.CharField(max_length=255)
    llegada_cod_local = models.CharField(max_length=10, null=True, blank=True)
    llegada_ruc = models.CharField(max_length=11, null=True, blank=True)

    # Transportista (obligatorio solo en mod_traslado 01 - público)
    transportista_tipo_doc = models.CharField(max_length=2, null=True, blank=True)
    transportista_num_doc = models.CharField(max_length=15, null=True, blank=True)
    transportista_nombre = models.CharField(max_length=255, null=True, blank=True)
    transportista_nro_mtc = models.CharField(max_length=20, null=True, blank=True)

    # Vehículo principal (placa basta en público; resto full en privado)
    vehiculo_placa = models.CharField(max_length=20)
    vehiculo_nro_circulacion = models.CharField(max_length=50, null=True, blank=True)
    vehiculo_nro_autorizacion = models.CharField(max_length=50, null=True, blank=True)
    vehiculo_cod_emisor = models.CharField(max_length=10, null=True, blank=True)
    vehiculo_secundarios = models.JSONField(default=list, blank=True)

    indicadores = models.JSONField(default=list, blank=True)
    contenedores = models.JSONField(default=list, blank=True)

    logo_url = models.URLField(max_length=500, null=True, blank=True)

    # --- Estado + respuesta API PHP ---
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="BORRADOR")
    estado_sunat = models.CharField(max_length=50, default="PENDIENTE", null=True, blank=True)
    ambiente = models.CharField(max_length=20, null=True, blank=True)  # BETA / PRODUCCION
    xml_url = models.URLField(max_length=500, null=True, blank=True)
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    cdr_url = models.URLField(max_length=500, null=True, blank=True)

    # Auditoría: qué envió el frontend/backend y qué respondió el PHP.
    payload_enviado = models.JSONField(default=dict, blank=True)
    respuesta_sunat = models.JSONField(default=dict, blank=True, null=True)

    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["-date_created"]
        verbose_name = "Guía de Remisión"
        verbose_name_plural = "Guías de Remisión"
        constraints = [
            models.UniqueConstraint(
                fields=["tienda", "serie", "correlativo"],
                name="uq_guia_tienda_serie_correlativo",
            )
        ]

    def __str__(self):
        return f"{self.serie}-{self.correlativo} ({self.get_mod_traslado_display()})"

    # ------------------------------------------------------------------
    # Helpers para la API PHP src/api/guia-remision-post.php
    # ------------------------------------------------------------------
    def _emisor_dict(self):
        t = self.tienda
        return {
            "ruc": t.ruc,
            "razonSocial": t.razon_social,
            "nombreComercial": self.emisor_nombre_comercial or t.nombre,
            "ubigeo": self.emisor_ubigeo,
            "departamento": self.emisor_departamento,
            "provincia": self.emisor_provincia,
            "distrito": self.emisor_distrito,
            "direccion": self.emisor_direccion or t.direccion,
            "certPriv": t.cert_clave_privada,
            "certPublic": t.cert_clave_publica,
            "userSol": t.sol_user,
            "claveSol": t.sol_password,
            "apiClientId": t.client_id,
            "apiClientSecret": t.client_secret,
        }

    def _envio_dict(self):
        envio = {
            "modTraslado": self.mod_traslado,
            "codTraslado": self.cod_traslado,
            "desTraslado": self.des_traslado,
            "fecTraslado": self.fec_traslado.isoformat() if self.fec_traslado else None,
            "pesoTotal": float(self.peso_total) if self.peso_total is not None else None,
            "undPesoTotal": self.und_peso_total,
            "partida": {
                "ubigeo": self.partida_ubigeo,
                "direccion": self.partida_direccion,
            },
            "llegada": {
                "ubigeo": self.llegada_ubigeo,
                "direccion": self.llegada_direccion,
            },
            "vehiculo": {"placa": self.vehiculo_placa},
            "conductores": [
                {
                    "tipo": c.tipo,
                    "tipoDoc": c.tipo_doc,
                    "nroDoc": c.nro_doc,
                    "nombres": c.nombres,
                    "apellidos": c.apellidos,
                    "licencia": c.licencia,
                }
                for c in self.conductores.all()
            ],
        }
        # Opcionales punto partida/llegada
        if self.partida_cod_local:
            envio["partida"]["codLocal"] = self.partida_cod_local
        if self.partida_ruc:
            envio["partida"]["ruc"] = self.partida_ruc
        if self.llegada_cod_local:
            envio["llegada"]["codLocal"] = self.llegada_cod_local
        if self.llegada_ruc:
            envio["llegada"]["ruc"] = self.llegada_ruc

        if self.peso_items is not None:
            envio["pesoItems"] = float(self.peso_items)
        if self.sustento_peso:
            envio["sustentoPeso"] = self.sustento_peso
        if self.num_bultos is not None:
            envio["numBultos"] = self.num_bultos
        if self.indicadores:
            envio["indicadores"] = self.indicadores
        if self.contenedores:
            envio["contenedores"] = self.contenedores

        if self.mod_traslado == "01":
            # Transporte PÚBLICO: transportista obligatorio.
            envio["transportista"] = {
                "tipoDoc": self.transportista_tipo_doc,
                "numDoc": self.transportista_num_doc,
                "nombre": self.transportista_nombre,
                "nroMtc": self.transportista_nro_mtc,
            }
        else:
            # Transporte PRIVADO: detalle completo del vehículo.
            veh = envio["vehiculo"]
            if self.vehiculo_nro_circulacion:
                veh["nroCirculacion"] = self.vehiculo_nro_circulacion
            if self.vehiculo_nro_autorizacion:
                veh["nroAutorizacion"] = self.vehiculo_nro_autorizacion
            if self.vehiculo_cod_emisor:
                veh["codEmisor"] = self.vehiculo_cod_emisor
            if self.vehiculo_secundarios:
                veh["secundarios"] = self.vehiculo_secundarios
        return envio

    def build_payload(self):
        """Arma el dict exacto que espera guia-remision-post.php."""
        payload = {
            "emisor": self._emisor_dict(),
            "serie": self.serie,
            "correlativo": self.correlativo,
            "fechaEmision": self.fecha_emision.strftime("%Y-%m-%d %H:%M:%S")
            if self.fecha_emision
            else None,
            "destinatario": {
                "tipoDoc": self.dest_tipo_doc,
                "numDoc": self.dest_num_doc,
                "nombre": self.dest_nombre,
                "direccion": self.dest_direccion,
            },
            "envio": self._envio_dict(),
            "items": [
                {
                    **{
                        "codigo": i.codigo,
                        "descripcion": i.descripcion,
                        "unidad": i.unidad,
                        "cantidad": float(i.cantidad),
                        "codProdSunat": i.cod_prod_sunat,
                    },
                    **({"atributos": i.atributos} if i.atributos else {}),
                }
                for i in self.items.all()
            ],
        }
        if self.observacion:
            payload["observacion"] = self.observacion
        if self.tercero_num_doc:
            payload["tercero"] = {
                "tipoDoc": self.tercero_tipo_doc,
                "numDoc": self.tercero_num_doc,
                "nombre": self.tercero_nombre,
            }
        if self.comprador_num_doc:
            payload["comprador"] = {
                "tipoDoc": self.comprador_tipo_doc,
                "numDoc": self.comprador_num_doc,
                "nombre": self.comprador_nombre,
            }
        docs = list(self.docs_relacionados.all())
        if docs:
            payload["docsRelacionados"] = [
                {"tipoDesc": d.tipo_desc, "tipo": d.tipo, "nro": d.nro, "emisor": d.emisor}
                for d in docs
            ]
        if self.logo_url:
            payload["logo_url"] = self.logo_url
        return payload

    def aplicar_respuesta(self, respuesta: dict):
        """Guarda URLs/estado devueltos por el PHP + payload enviado. Retorna self."""
        self.respuesta_sunat = respuesta
        self.numero_guia = respuesta.get("guia") or self.numero_guia
        self.ambiente = respuesta.get("ambiente") or self.ambiente
        self.xml_url = respuesta.get("xml_url") or self.xml_url
        self.pdf_url = respuesta.get("pdf_url") or self.pdf_url
        self.cdr_url = respuesta.get("cdr_url") or self.cdr_url
        # Si el PHP confirma aceptación, marcarla.
        if self.xml_url or self.numero_guia:
            self.estado = "ACEPTADO"
            self.estado_sunat = "Aceptado"
        self.save(
            update_fields=[
                "respuesta_sunat", "numero_guia", "ambiente",
                "xml_url", "pdf_url", "cdr_url", "estado", "estado_sunat",
            ]
        )
        return self


class GuiaRemisionItem(models.Model):
    guia = models.ForeignKey(GuiaRemision, on_delete=models.CASCADE, related_name="items")
    codigo = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=255)
    unidad = models.CharField(max_length=10, default="NIU")
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    cod_prod_sunat = models.CharField(max_length=50, null=True, blank=True)
    atributos = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.codigo} x{self.cantidad}"

    class Meta:
        ordering = ["id"]


class GuiaDocumentoRelacionado(models.Model):
    guia = models.ForeignKey(
        GuiaRemision, on_delete=models.CASCADE, related_name="docs_relacionados"
    )
    tipo_desc = models.CharField(max_length=50, default="Factura")  # ej Factura
    tipo = models.CharField(max_length=2)  # 01 factura, 03 boleta, etc.
    nro = models.CharField(max_length=30)  # ej F001-1
    emisor = models.CharField(max_length=11, null=True, blank=True)

    def __str__(self):
        return f"{self.tipo} {self.nro}"

    class Meta:
        ordering = ["id"]


class GuiaRemisionConductor(models.Model):
    TIPO_CHOICES = [("Principal", "Principal"), ("Secundario", "Secundario")]

    guia = models.ForeignKey(
        GuiaRemision, on_delete=models.CASCADE, related_name="conductores"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="Principal")
    # Catálogo 06 SUNAT: un solo carácter (1=DNI, 6=RUC, 4, 7, A, 0). Sin cero a la izquierda.
    tipo_doc = models.CharField(max_length=2, default="1")
    nro_doc = models.CharField(max_length=15)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    licencia = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.tipo}: {self.nombres} {self.apellidos}"

    class Meta:
        ordering = ["id"]
