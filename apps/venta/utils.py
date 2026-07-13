from decimal import Decimal
from num2words import num2words
from apps.comprobante.models import ComprobanteElectronico, NotaCreditoDB
from apps.venta.models import VentaProducto
from apps.cliente.models import Cliente
from apps.inventario.models import Inventario


class ClienteService:
    ANONYMOUS_CLIENTE = {
        "numero": "00000000",
        "nombre_o_razon_social": "CLIENTE ANÓNIMO",
        "nombre_completo": "CLIENTE ANÓNIMO",
        "email_cliente": None,
        "telefono_cliente": None,
        "direccion_cliente": None,
    }

    @staticmethod
    def resolve_cliente(cliente_data, tienda):
        if not cliente_data:
            return ClienteService.ANONYMOUS_CLIENTE

        documento = (
            cliente_data.get("numero")
            or cliente_data.get("ruc")
            or cliente_data.get("documento_cliente")
        )

        if not documento:
            return ClienteService.ANONYMOUS_CLIENTE

        Cliente.objects.get_or_create(
            document=documento,
            tienda=tienda,
            defaults={
                "fullname": cliente_data.get("nombre_completo"),
                "firstname": cliente_data.get("nombre_o_razon_social"),
                "address": cliente_data.get("direccion_cliente"),
                "phone": cliente_data.get("telefono_cliente"),
                "email": cliente_data.get("correo_cliente"),
            }
        )

        return cliente_data


class InventarioService:

    @staticmethod
    def validate_and_lock_stock(productos_data):
        from .exceptions import InventarioNoEncontradoError, StockInsuficienteError

        items_locked = []
        errores = []

        for item in productos_data:
            try:
                inventario = Inventario.objects.select_for_update().get(
                    id=item["inventarioId"]
                )
            except Inventario.DoesNotExist:
                raise InventarioNoEncontradoError(item["inventarioId"])

            cantidad = int(item["cantidad_final"])

            if inventario.cantidad < cantidad:
                errores.append(
                    f"Stock insuficiente para '{inventario.producto.nombre}'. "
                    f"Disponible: {inventario.cantidad}, solicitado: {cantidad}"
                )
                continue

            items_locked.append((inventario, cantidad))

        if errores:
            raise StockInsuficienteError(errores)

        return items_locked

    @staticmethod
    def deduct_stock(items_locked):
        for inventario, cantidad in items_locked:
            inventario.cantidad -= cantidad
            inventario.save()


class VentaService:
    PORCENTAJE_IGV = Decimal("18.00")
    FACTOR_IGV = PORCENTAJE_IGV / Decimal("100.00")

    @staticmethod
    def calcular_producto(item, inventario, cantidad):
        descuento = Decimal(item["descuento"])
        precio_unitario_original = Decimal(inventario.costo_venta)
        precio_unitario = precio_unitario_original - (descuento / cantidad)
        valor_unitario = precio_unitario / (Decimal("1.00") + VentaService.FACTOR_IGV)
        valor_venta = valor_unitario * cantidad
        igv = valor_venta * VentaService.FACTOR_IGV

        return {
            "producto": inventario.producto,
            "cantidad": cantidad,
            "descuento": descuento,
            "precio_unitario_original": precio_unitario_original,
            "precio_unitario": precio_unitario,
            "valor_unitario": valor_unitario,
            "valor_venta": valor_venta,
            "igv": igv,
        }

    @staticmethod
    def create_venta_producto(venta, calculo):
        return VentaProducto.objects.create(
            venta=venta,
            producto=calculo["producto"],
            cantidad=calculo["cantidad"],
            valor_unitario=calculo["valor_unitario"],
            valor_venta=calculo["valor_venta"],
            base_igv=calculo["valor_venta"],
            porcentaje_igv=VentaService.PORCENTAJE_IGV,
            igv=calculo["igv"],
            tipo_afectacion_igv="10",
            total_impuestos=calculo["igv"],
            precio_unitario=calculo["precio_unitario"],
            descuento=calculo["descuento"],
            costo_original=calculo["precio_unitario_original"],
        )

    @staticmethod
    def build_producto_registrado(calculo):
        producto = calculo["producto"]
        return {
            "producto_id": producto.id,
            "producto_nombre": producto.nombre,
            "cantidad": calculo["cantidad"],
            "valor_unitario": float(calculo["valor_unitario"]),
            "valor_venta": float(calculo["valor_venta"]),
            "igv": float(calculo["igv"]),
            "precio_unitario": float(calculo["precio_unitario"]),
            "costo_original": float(calculo["precio_unitario_original"]),
            "descuento": float(calculo["descuento"]),
        }

    @staticmethod
    def build_item_sunat(calculo):
        producto = calculo["producto"]
        return {
            "codigo": producto.sku,
            "unidad": "NIU",
            "descripcion": producto.nombre,
            "cantidad": calculo["cantidad"],
            "valorUnitario": round(float(calculo["valor_unitario"]), 2),
            "valorVenta": round(float(calculo["valor_venta"]), 2),
            "baseIgv": round(float(calculo["valor_venta"]), 2),
            "porcentajeIgv": 18,
            "igv": round(float(calculo["igv"]), 2),
            "tipoAfectacionIgv": "10",
            "totalImpuestos": round(float(calculo["igv"]), 2),
            "precioUnitario": round(float(calculo["precio_unitario"]), 2),
        }


class ComprobanteService:

    @staticmethod
    def get_siguiente(tipo_comprobante, tienda):
        tipo = tipo_comprobante.lower()
        numero_serie = tienda.serie or "001"

        if tipo == "factura":
            serie_base = f"F{numero_serie}"
            correlativo_inicial = tienda.correlativo_inicial_factura or 1
        else:
            serie_base = f"B{numero_serie}"
            correlativo_inicial = tienda.correlativo_inicial_boleta or 1

        ultimo = (
            ComprobanteElectronico.objects
            .filter(venta__tienda=tienda, serie=serie_base)
            .order_by('-correlativo')
            .first()
        )

        if ultimo:
            correlativo_actual = int(ultimo.correlativo)
            nuevo_correlativo = str(correlativo_actual + 1).zfill(8)
        else:
            nuevo_correlativo = str(correlativo_inicial).zfill(8)

        return serie_base, nuevo_correlativo

    @staticmethod
    def get_siguiente_nota_credito(tipo_comprobante_modifica, tienda):
        tipo = tipo_comprobante_modifica.lower()
        numero_serie = tienda.serie or "001"

        if tipo == "factura":
            serie_base = f"F{numero_serie}"
        elif tipo in ["boleta", "anonima"]:
            serie_base = f"B{numero_serie}"
        else:
            raise ValueError("Tipo de comprobante inválido")

        correlativo_inicial = tienda.correlativo_inicial_nota_credito or 1

        ultimo = (
            NotaCreditoDB.objects
            .filter(venta__tienda=tienda, serie=serie_base)
            .order_by('-correlativo')
            .first()
        )

        if ultimo:
            correlativo_actual = int(ultimo.correlativo)
            if correlativo_actual >= 99999999:
                raise ValueError(f"Correlativo máximo alcanzado para la serie {serie_base}")
            nuevo_correlativo = str(correlativo_actual + 1).zfill(8)
        else:
            nuevo_correlativo = str(correlativo_inicial).zfill(8)

        return serie_base, nuevo_correlativo


class SunatService:

    @staticmethod
    def generate_leyenda(monto):
        return f"SON {num2words(monto, lang='es').upper()} CON 00/100 SOLES"

    @staticmethod
    def get_php_url(tipo_comprobante):
        from core.settings import SUNAT_PHP
        base = SUNAT_PHP.rstrip("/")
        if tipo_comprobante == "Factura":
            return f"{base}/src/api/factura-post.php"
        return f"{base}/src/api/boleta-post.php"

    @staticmethod
    def build_comprobante_data(venta, tienda, serie, correlativo, gravado_total, igv_total, subtotal, total, leyenda, productos_items_for_sunat):
        return {
            "serie": serie,
            "correlativo": correlativo,
            "moneda": "PEN",
            "gravadas": float(gravado_total),
            "exoneradas": 0.0,
            "igv": float(igv_total),
            "valorVenta": float(subtotal),
            "subTotal": float(subtotal + igv_total),
            "total": float(total),
            "leyenda": leyenda,
            "cliente": {
                "tipoDoc": venta.tipo_documento_cliente,
                "numDoc": venta.numero_documento_cliente,
                "nombre": venta.nombre_cliente,
            },
            "items": productos_items_for_sunat,
            "emisor": {
                "ruc": tienda.ruc,
                "razonSocial": tienda.razon_social,
                "nombreComercial": tienda.nombre,
                "ubigeo": "150101",
                "departamento": "LIMA",
                "provincia": "LIMA",
                "distrito": "LIMA",
                "urbanizacion": "-",
                "direccion": tienda.direccion or "-",
            },
        }

    @staticmethod
    def send_to_sunat(comprobante_data, tipo_comprobante):
        import requests
        from .exceptions import SunatError

        php_url = SunatService.get_php_url(tipo_comprobante)
        try:
            response = requests.post(
                php_url,
                json=comprobante_data,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise SunatError("No se pudo conectar al servidor de SUNAT")
        except requests.exceptions.Timeout:
            raise SunatError("Tiempo de espera agotado al conectar con SUNAT")
        except requests.exceptions.RequestException as e:
            raise SunatError(str(e))

        try:
            return response.json()
        except ValueError:
            raise SunatError("Respuesta inválida del servidor de SUNAT")

    @staticmethod
    def process_sunat_response(response_json, comprobante, venta):
        from .exceptions import SunatRechazadoError

        cdr_codigo = response_json.get("cdr_codigo")

        if cdr_codigo == "0":
            comprobante.estado_sunat = "ACEPTADO"
            venta.estado = "ACEPTADO"
        else:
            comprobante.estado_sunat = "RECHAZADO"
            venta.estado = "RECHAZADO"
            mensaje_error = response_json.get("error", "")
            raise SunatRechazadoError(cdr_codigo, mensaje_error)

        comprobante.save(update_fields=["estado_sunat"])
        venta.save(update_fields=["estado"])

        comprobante.xml_url = response_json.get("xml_url")
        comprobante.pdf_url = response_json.get("pdf_url")
        comprobante.cdr_url = response_json.get("cdr_url")
        comprobante.ticket_url = response_json.get("ticket_url")
        comprobante.save(update_fields=["xml_url", "pdf_url", "cdr_url", "ticket_url"])

    @staticmethod
    def build_comprobante_response(comprobante, response_json):
        return {
            "tipo_comprobante": comprobante.tipo_comprobante,
            "serie": comprobante.serie,
            "correlativo": comprobante.correlativo,
            "moneda": comprobante.moneda,
            "gravadas": float(comprobante.gravadas),
            "igv": float(comprobante.igv),
            "valorVenta": float(comprobante.valorVenta),
            "sub_total": float(comprobante.sub_total),
            "total": float(comprobante.total),
            "leyenda": comprobante.leyenda,
            "tipo_documento_cliente": comprobante.tipo_documento_cliente,
            "numero_documento_cliente": comprobante.numero_documento_cliente,
            "nombre_cliente": comprobante.nombre_cliente,
            "estado_sunat": comprobante.estado_sunat,
            "xml_url": comprobante.xml_url,
            "pdf_url": comprobante.pdf_url,
            "cdr_url": comprobante.cdr_url,
            "ticket_url": comprobante.ticket_url,
            "items": comprobante.items,
            "error_sunat": response_json.get("error"),
        }
