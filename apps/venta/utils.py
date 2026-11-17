from decimal import Decimal, InvalidOperation
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
    def build_cliente_json(cliente_data, venta, email_val=None, telefono_val=None, direccion_val=None):
        """Construye snapshot completo del cliente para guardar en Venta.cliente_json."""
        raw = cliente_data or {}
        return {
            "numero": raw.get("numero") or raw.get("ruc") or raw.get("documento_cliente") or venta.numero_documento_cliente,
            "ruc": raw.get("ruc"),
            "documento_cliente": raw.get("documento_cliente"),
            "nombre_completo": raw.get("nombre_completo") or venta.nombre_cliente,
            "nombre_o_razon_social": raw.get("nombre_o_razon_social") or venta.nombre_cliente,
            "nombre": venta.nombre_cliente,
            "tipo_documento": venta.tipo_documento_cliente,
            "numero_documento": venta.numero_documento_cliente,
            "email": email_val or venta.email_cliente or raw.get("correo_cliente") or raw.get("email_cliente"),
            "correo_cliente": email_val or venta.email_cliente or raw.get("correo_cliente"),
            "telefono": telefono_val or venta.telefono_cliente or raw.get("telefono_cliente"),
            "telefono_cliente": telefono_val or venta.telefono_cliente or raw.get("telefono_cliente"),
            "direccion": direccion_val or venta.direccion_cliente or raw.get("direccion_cliente"),
            "direccion_cliente": direccion_val or venta.direccion_cliente or raw.get("direccion_cliente"),
            "raw": raw,
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

        # Siempre tomar direccion/telefono/correo y actualizar cliente si ya existe
        defaults = {
            "fullname": cliente_data.get("nombre_completo"),
            "firstname": cliente_data.get("nombre_o_razon_social"),
            "address": cliente_data.get("direccion_cliente"),
            "phone": cliente_data.get("telefono_cliente"),
            "email": cliente_data.get("correo_cliente"),
        }
        # También permitir keys alternativas que usa el frontend en Venta (correo vs email)
        if not defaults["email"]:
            defaults["email"] = cliente_data.get("email_cliente") or cliente_data.get("email")
        if not defaults["phone"]:
            defaults["phone"] = cliente_data.get("phone") or cliente_data.get("celular")
        # fallback: si el frontend manda correo/tel/direccion a nivel top-level, también los tomamos
        # (los inyectamos si cliente_data no los traía)
        # Nota: la actualización real del Cliente se hace siempre que haya valor

        cliente, created = Cliente.objects.get_or_create(
            document=documento,
            tienda=tienda,
            defaults={k: v for k, v in defaults.items() if v not in (None, "")},
        )
        if not created:
            # Actualizar siempre direccion/telefono/correo si vienen con valor
            to_update = {}
            if cliente_data.get("direccion_cliente") not in (None, ""):
                to_update["address"] = cliente_data.get("direccion_cliente")
            if cliente_data.get("telefono_cliente") not in (None, ""):
                to_update["phone"] = cliente_data.get("telefono_cliente")
            if cliente_data.get("correo_cliente") not in (None, ""):
                to_update["email"] = cliente_data.get("correo_cliente")
            # también actualizar nombre si cambió
            if cliente_data.get("nombre_completo") not in (None, "") and cliente_data.get("nombre_completo") != cliente.fullname:
                to_update["fullname"] = cliente_data.get("nombre_completo")
            if cliente_data.get("nombre_o_razon_social") not in (None, "") and cliente_data.get("nombre_o_razon_social") != cliente.firstname:
                to_update["firstname"] = cliente_data.get("nombre_o_razon_social")
            if to_update:
                for k, v in to_update.items():
                    setattr(cliente, k, v)
                cliente.save(update_fields=list(to_update.keys()))

        return cliente_data


class InventarioService:

    @staticmethod
    def _celular_id_de_item(item):
        """ID de celular si el item es venta por IMEI (celular_id o inventarioId 'celular-<id>')."""
        from .exceptions import DatosInvalidosError

        cid = item.get("celular_id")
        if cid is None and item.get("es_celular"):
            cid = item.get("celularId")
        if cid is not None and cid != "":
            try:
                return int(cid)
            except (ValueError, TypeError):
                raise DatosInvalidosError("celular_id", f"celular_id inválido: {cid}")
        inv = item.get("inventarioId")
        if isinstance(inv, str) and inv.startswith("celular-"):
            try:
                return int(inv.split("-", 1)[1])
            except (ValueError, TypeError):
                raise DatosInvalidosError("inventarioId", f"Referencia de celular inválida: {inv}")
        return None

    @staticmethod
    def validate_and_lock_stock(productos_data, tienda=None):
        from .exceptions import InventarioNoEncontradoError, StockInsuficienteError, DatosInvalidosError

        items_locked = []
        errores = []

        for idx, item in enumerate(productos_data):
            raw_cant = item.get("cantidad_final")
            if raw_cant is None or raw_cant == "":
                raise DatosInvalidosError("cantidad_final", f"Item #{idx+1} sin cantidad")
            try:
                cantidad = int(raw_cant)
            except (ValueError, TypeError):
                raise DatosInvalidosError("cantidad_final", f"Item #{idx+1} valor inválido: {raw_cant}")
            if cantidad <= 0:
                raise DatosInvalidosError("cantidad_final", f"Item #{idx+1} debe ser > 0, recibido {cantidad}")

            celular_id = InventarioService._celular_id_de_item(item)
            if celular_id is not None:
                items_locked.append(("celular", InventarioService._lock_celular(idx, celular_id, cantidad, tienda), cantidad))
                continue

            inv_id = item.get("inventarioId")
            if inv_id is None:
                raise DatosInvalidosError("inventarioId", f"Item #{idx+1} sin inventarioId")

            try:
                inventario = Inventario.objects.select_for_update().get(id=inv_id)
            except Inventario.DoesNotExist:
                raise InventarioNoEncontradoError(inv_id)

            # Validación temprana de precio para dar mensaje claro antes de VentaService
            if inventario.costo_venta is None:
                raise DatosInvalidosError(
                    "costo_venta",
                    f"El producto '{inventario.producto.nombre}' (inventario {inv_id}) no tiene precio de venta configurado"
                )

            if inventario.cantidad < cantidad:
                errores.append(
                    f"Stock insuficiente para '{inventario.producto.nombre}'. "
                    f"Disponible: {inventario.cantidad}, solicitado: {cantidad}"
                )
                continue

            items_locked.append(("inventario", inventario, cantidad))

        if errores:
            raise StockInsuficienteError(errores)

        return items_locked

    @staticmethod
    def _lock_celular(idx, celular_id, cantidad, tienda=None):
        """Valida y bloquea un celular para venta por IMEI (unidad única)."""
        from apps.celular.models import Celular
        from .exceptions import InventarioNoEncontradoError, StockInsuficienteError, DatosInvalidosError

        if cantidad != 1:
            raise DatosInvalidosError("cantidad_final", f"Item #{idx+1}: el celular se vende por unidad (cantidad 1)")

        qs = Celular.objects.select_for_update()
        if tienda is not None and getattr(tienda, "id", None):
            qs = qs.filter(tienda_id=tienda.id)
        try:
            celular = qs.get(id=celular_id)
        except Celular.DoesNotExist:
            raise InventarioNoEncontradoError(f"celular-{celular_id}")

        if not celular.activo or celular.is_deleted:
            raise DatosInvalidosError("celular_id", f"Item #{idx+1}: el celular ya no está disponible para la venta")
        # Un IMEI vendido no se puede volver a vender, aunque lo reactiven manualmente.
        if InventarioService._imei_vendido(celular, getattr(tienda, "id", None) if tienda else None):
            raise StockInsuficienteError([f"El celular con IMEI {celular.imei1} ya fue vendido y no se puede vender de nuevo"])
        if not celular.disponible:
            raise StockInsuficienteError([f"El celular {celular.marca} {celular.modelo} (IMEI {celular.imei1}) ya fue vendido"])
        if celular.precio_venta is None or Decimal(str(celular.precio_venta)) <= 0:
            raise DatosInvalidosError(
                "costo_venta",
                f"El celular {celular.marca} {celular.modelo} (IMEI {celular.imei1}) no tiene precio de venta configurado"
            )
        return celular

        if errores:
            raise StockInsuficienteError(errores)

        return items_locked

    @staticmethod
    def _imei_vendido(celular, tienda_id=None):
        """True si alguno de los IMEI actuales ya se vendió (aunque reactiven el equipo)."""
        from django.db.models import Q
        from apps.venta.models import VentaProducto

        imeis = [i for i in (celular.imei1, celular.imei2) if i]
        if not imeis:
            return False
        consulta = Q(imei__in=imeis)
        if tienda_id:
            consulta &= Q(venta__tienda_id=tienda_id)
        return VentaProducto.objects.filter(consulta).exists()

    @staticmethod
    def deduct_stock(items_locked):
        for locked in items_locked:
            kind, registro, cantidad = locked[0], locked[1], locked[2]
            if kind == "celular":
                registro.disponible = False
                registro.save(update_fields=["disponible"])
            else:
                registro.cantidad -= cantidad
                registro.save()


class VentaService:
    PORCENTAJE_IGV = Decimal("18.00")
    FACTOR_IGV = PORCENTAJE_IGV / Decimal("100.00")

    @staticmethod
    def calcular_producto(item, registro, cantidad):
        from .exceptions import DatosInvalidosError

        # descuento puede venir como None, "", numero o string
        raw_desc = item.get("descuento", 0)
        if raw_desc is None or raw_desc == "":
            raw_desc = "0"
        try:
            descuento = Decimal(str(raw_desc))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise DatosInvalidosError("descuento", f"Valor '{raw_desc}' no es un número válido: {e}")

        if descuento < 0:
            raise DatosInvalidosError("descuento", "El descuento no puede ser negativo")

        # ---- Venta por IMEI (celular, unidad única) ----
        try:
            from apps.celular.models import Celular
            es_celular = isinstance(registro, Celular)
        except Exception:
            es_celular = False
        if es_celular:
            return VentaService._calcular_celular(item, registro, cantidad, descuento)

        inventario = registro
        if inventario.costo_venta is None:
            raise DatosInvalidosError(
                "costo_venta",
                f"El producto '{inventario.producto.nombre}' no tiene precio de venta configurado"
            )
        try:
            precio_unitario_original = Decimal(str(inventario.costo_venta))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise DatosInvalidosError("costo_venta", f"Precio inválido '{inventario.costo_venta}': {e}")

        if cantidad <= 0:
            raise DatosInvalidosError("cantidad_final", "La cantidad debe ser mayor a 0")

        # descuento prorrateado; evitar división por cero ya validada
        precio_unitario = precio_unitario_original - (descuento / Decimal(cantidad))
        if precio_unitario < 0:
            raise DatosInvalidosError("descuento", f"Descuento {descuento} excede precio {precio_unitario_original} x {cantidad}")

        valor_unitario = precio_unitario / (Decimal("1.00") + VentaService.FACTOR_IGV)
        valor_venta = valor_unitario * Decimal(cantidad)
        igv = valor_venta * VentaService.FACTOR_IGV

        # Snapshot de compra para detectar actualizaciones (no afecta cálculo)
        try:
            costo_compra_snap = Decimal(str(inventario.costo_compra)) if inventario.costo_compra is not None else None
        except Exception:
            costo_compra_snap = None
        # categoria snapshot
        cat = inventario.producto.categoria if hasattr(inventario.producto, "categoria") else None
        return {
            "producto": inventario.producto,
            "inventario": inventario,
            "celular": None,
            "tipo": "inventario",
            "cantidad": cantidad,
            "descuento": descuento,
            "precio_unitario_original": precio_unitario_original,
            "precio_unitario": precio_unitario,
            "valor_unitario": valor_unitario,
            "valor_venta": valor_venta,
            "igv": igv,
            "costo_compra": costo_compra_snap,
            "categoria_id": cat.id if cat else None,
            "categoria_nombre": cat.nombre if cat else None,
            "descripcion_sunat": inventario.producto.nombre,
            "codigo_sunat": inventario.producto.sku,
        }

    @staticmethod
    def _descripcion_celular(celular):
        base = f"{celular.marca} {celular.modelo} {celular.memoria or ''}".strip()
        base = " ".join(base.split())
        imeis = f"IMEI: {celular.imei1}"
        if celular.imei2:
            imeis += f" / IMEI2: {celular.imei2}"
        return f"{base} - {imeis}"

    @staticmethod
    def _calcular_celular(item, celular, cantidad, descuento):
        from .exceptions import DatosInvalidosError

        if cantidad != 1:
            raise DatosInvalidosError("cantidad_final", "El celular se vende por unidad (cantidad 1)")
        try:
            precio_unitario_original = Decimal(str(celular.precio_venta))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise DatosInvalidosError("costo_venta", f"Precio inválido '{celular.precio_venta}': {e}")
        if precio_unitario_original <= 0:
            raise DatosInvalidosError(
                "costo_venta",
                f"El celular {celular.marca} {celular.modelo} (IMEI {celular.imei1}) no tiene precio de venta configurado"
            )

        precio_unitario = precio_unitario_original - (descuento / Decimal(cantidad))
        if precio_unitario < 0:
            raise DatosInvalidosError("descuento", f"Descuento {descuento} excede precio actual {precio_unitario_original} x {cantidad} (IMEI {celular.imei1})")

        valor_unitario = precio_unitario / (Decimal("1.00") + VentaService.FACTOR_IGV)
        valor_venta = valor_unitario * Decimal(cantidad)
        igv = valor_venta * VentaService.FACTOR_IGV

        try:
            costo_compra_snap = Decimal(str(celular.costo_compra)) if celular.costo_compra is not None else None
        except Exception:
            costo_compra_snap = None
        descripcion = VentaService._descripcion_celular(celular)
        return {
            "producto": None,
            "inventario": None,
            "celular": celular,
            "tipo": "celular",
            "cantidad": cantidad,
            "descuento": descuento,
            "precio_unitario_original": precio_unitario_original,
            "precio_unitario": precio_unitario,
            "valor_unitario": valor_unitario,
            "valor_venta": valor_venta,
            "igv": igv,
            "costo_compra": costo_compra_snap,
            "categoria_id": None,
            "categoria_nombre": "Celulares",
            "descripcion_sunat": descripcion,
            "codigo_sunat": celular.imei1,
        }

    @staticmethod
    def create_venta_producto(venta, calculo):
        celular = calculo.get("celular")
        return VentaProducto.objects.create(
            venta=venta,
            producto=calculo["producto"],
            celular=celular,
            imei=celular.imei1 if celular else None,
            descripcion=calculo.get("descripcion_sunat"),
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
    def _is_deleted(producto):
        """True si el producto fue eliminado (soft delete)."""
        if producto is None:
            return True
        # activo=False -> eliminado (DeleteProductoAPIView)
        if not getattr(producto, "activo", True):
            return True
        nombre = getattr(producto, "nombre", "") or ""
        if "(Delete)" in nombre:
            return True
        return False

    @staticmethod
    def _is_categoria_deleted(categoria):
        """True si la categoría fue eliminada (soft delete: activo=False o '(Delete)' en nombre).

        A diferencia de producto, categoria None significa 'sin categoría', no eliminada.
        """
        if categoria is None:
            return False
        # activo=False -> eliminada (DeactivateCategoria/DeleteCategoria)
        if not getattr(categoria, "activo", True):
            return True
        nombre = getattr(categoria, "nombre", "") or ""
        if "(Delete)" in nombre:
            return True
        return False

    @staticmethod
    def _check_updated(snapshot, producto, inventario):
        """Compara snapshot vs estado actual. Retorna (is_updated, updated_fields)."""
        # Snapshot de celular: solo importa el precio de venta (el IMEI no cambia).
        if snapshot.get("celular_id") is not None:
            try:
                from apps.celular.models import Celular
                cel = Celular.objects.filter(id=snapshot.get("celular_id")).first()
            except Exception:
                cel = None
            if cel is None or not getattr(cel, "activo", True) or getattr(cel, "is_deleted", False):
                return False, []
            snap_pv = snapshot.get("precio_venta", snapshot.get("costo_original"))
            if snap_pv is not None:
                try:
                    if Decimal(str(snap_pv)).quantize(Decimal("0.01")) != Decimal(str(cel.precio_venta)).quantize(Decimal("0.01")):
                        return True, ["precio_venta"]
                except Exception:
                    pass
            return False, []
        updated = []
        if producto is None or VentaService._is_deleted(producto):
            return False, updated  # ya es deleted, no marcar como updated
        # nombre
        snap_nombre = snapshot.get("producto_nombre")
        if snap_nombre is not None and snap_nombre != producto.nombre:
            updated.append("nombre")
        # categoria (comparar id)
        snap_cat = snapshot.get("categoria_id")
        curr_cat = producto.categoria_id if hasattr(producto, "categoria_id") else None
        # solo comparar si snapshot tenía categoria (ventas nuevas)
        if snap_cat is not None and curr_cat != snap_cat:
            updated.append("categoria")
        # también nombre de categoria por si cambió nombre
        snap_cat_nombre = snapshot.get("categoria_nombre")
        curr_cat_nombre = producto.categoria.nombre if getattr(producto, "categoria", None) else None
        if snap_cat is not None and snap_cat_nombre is not None and curr_cat_nombre != snap_cat_nombre:
            if "categoria" not in updated:
                updated.append("categoria")
        # precio venta -> inventario.costo_venta
        snap_pv = snapshot.get("costo_original")
        # fallback viejo: snapshot puede tener precio_venta
        if snap_pv is None:
            snap_pv = snapshot.get("precio_venta")
        if snap_pv is not None and inventario is not None and inventario.costo_venta is not None:
            try:
                if Decimal(str(snap_pv)).quantize(Decimal("0.01")) != Decimal(str(inventario.costo_venta)).quantize(Decimal("0.01")):
                    updated.append("precio_venta")
            except Exception:
                if str(snap_pv) != str(inventario.costo_venta):
                    updated.append("precio_venta")
        elif snap_pv is not None and inventario is None:
            # inventario no encontrado -> considerar eliminado, no updated
            pass
        # precio compra
        snap_pc = snapshot.get("precio_compra")
        # snapshot viejo puede tener costo_compra
        if snap_pc is None:
            snap_pc = snapshot.get("costo_compra")
        if snap_pc is not None and inventario is not None and inventario.costo_compra is not None:
            try:
                if Decimal(str(snap_pc)).quantize(Decimal("0.01")) != Decimal(str(inventario.costo_compra)).quantize(Decimal("0.01")):
                    updated.append("precio_compra")
            except Exception:
                if str(snap_pc) != str(inventario.costo_compra):
                    updated.append("precio_compra")
        # sku cambio (opcional, indica re-categorización)
        snap_sku = snapshot.get("sku")
        if snap_sku is not None and snap_sku != getattr(producto, "sku", None):
            updated.append("sku")
        return len(updated) > 0, updated

    @staticmethod
    def build_producto_registrado(calculo, request=None, inventario=None):
        cel = calculo.get("celular")
        if cel is not None:
            return VentaService._snapshot_celular(calculo, cel, request)
        producto = calculo["producto"]
        # inventario puede venir en calculo["inventario"] o param
        inv = inventario or calculo.get("inventario")
        img_url = None
        producto_imagen = None
        try:
            if producto and getattr(producto, "imagen", None):
                if hasattr(producto.imagen, "url") and producto.imagen:
                    url = producto.imagen.url
                    producto_imagen = url
                    if request is not None:
                        try:
                            img_url = request.build_absolute_uri(url)
                        except Exception:
                            img_url = url
                    else:
                        img_url = url
        except Exception:
            img_url = None
            producto_imagen = None
        is_deleted = VentaService._is_deleted(producto)
        # snapshot info para detectar updates futuros
        categoria = getattr(producto, "categoria", None) if producto else None
        cat_id = categoria.id if categoria else calculo.get("categoria_id")
        cat_nombre = categoria.nombre if categoria else calculo.get("categoria_nombre")
        cat_color = getattr(categoria, "color", None) if categoria is not None else None
        cat_imagen = None
        try:
            if categoria is not None and getattr(categoria, "imagen", None):
                if hasattr(categoria.imagen, "url") and categoria.imagen:
                    cat_imagen = categoria.imagen.url
        except Exception:
            cat_imagen = None
        categoria_data = {
            "categoria_id": cat_id,
            "nombre": cat_nombre,
            "descripcion": getattr(categoria, "descripcion", None) if categoria is not None else None,
            "color": cat_color,
            "imagen": cat_imagen,
            "activo": getattr(categoria, "activo", True) if categoria is not None else True,
            "is_deleted": VentaService._is_categoria_deleted(categoria),
        }
        # precio compra snapshot
        precio_compra = None
        if calculo.get("costo_compra") is not None:
            try:
                precio_compra = float(calculo.get("costo_compra"))
            except Exception:
                precio_compra = None
        elif inv is not None and getattr(inv, "costo_compra", None) is not None:
            try:
                precio_compra = float(inv.costo_compra)
            except Exception:
                precio_compra = None
        return {
            "producto_id": producto.id if producto else None,
            "producto_nombre": producto.nombre if producto else None,
            "cantidad": calculo["cantidad"],
            "valor_unitario": float(calculo["valor_unitario"]),
            "valor_venta": float(calculo["valor_venta"]),
            "igv": float(calculo["igv"]),
            "precio_unitario": float(calculo["precio_unitario"]),
            "costo_original": float(calculo["precio_unitario_original"]),
            "precio_venta": float(calculo["precio_unitario_original"]),
            "descuento": float(calculo["descuento"]),
            "sku": getattr(producto, "sku", None) if producto else None,
            "categoria_id": cat_id,
            "categoria_nombre": cat_nombre,
            "categoria_color": cat_color,
            "categoria_data": categoria_data,
            "precio_compra": precio_compra,
            "costo_compra": precio_compra,
            "producto_imagen": producto_imagen,
            "img_url": img_url,
            "imagen": img_url,
            "is_deleted": is_deleted,
            "producto_activo": not is_deleted,
            "producto_existe": producto is not None and not is_deleted,
            "is_updated": False,
            "updated_fields": [],
        }

    @staticmethod
    def _snapshot_celular(calculo, celular, request=None):
        """Snapshot de un celular vendido (producto_id queda en None a propósito)."""
        img_url = None
        try:
            if getattr(celular, "imagen1", None) and hasattr(celular.imagen1, "url") and celular.imagen1:
                url = celular.imagen1.url
                img_url = request.build_absolute_uri(url) if request and url else url
        except Exception:
            img_url = None
        descripcion = calculo.get("descripcion_sunat") or VentaService._descripcion_celular(celular)
        try:
            precio_compra = float(calculo.get("costo_compra")) if calculo.get("costo_compra") is not None else None
        except Exception:
            precio_compra = None
        return {
            "producto_id": None,
            "celular_id": celular.id,
            "imei": celular.imei1,
            "producto_nombre": descripcion,
            "cantidad": calculo["cantidad"],
            "valor_unitario": float(calculo["valor_unitario"]),
            "valor_venta": float(calculo["valor_venta"]),
            "igv": float(calculo["igv"]),
            "precio_unitario": float(calculo["precio_unitario"]),
            "costo_original": float(calculo["precio_unitario_original"]),
            "precio_venta": float(calculo["precio_unitario_original"]),
            "descuento": float(calculo["descuento"]),
            "sku": celular.imei1,
            "categoria_id": None,
            "categoria_nombre": "Celulares",
            "categoria_color": None,
            "categoria_data": {
                "categoria_id": None,
                "nombre": "Celulares",
                "descripcion": "Venta por IMEI",
                "color": None,
                "imagen": None,
                "activo": True,
                "is_deleted": False,
            },
            "precio_compra": precio_compra,
            "costo_compra": precio_compra,
            "producto_imagen": img_url,
            "img_url": img_url,
            "imagen": img_url,
            "is_deleted": False,
            "producto_activo": True,
            "producto_existe": True,
            "is_updated": False,
            "updated_fields": [],
        }

    @staticmethod
    def _enriquecer_celular(item, celular_id, venta=None):
        """Estado live de un item celular (no pasa por Producto/Inventario)."""
        try:
            from apps.celular.models import Celular
            qs = Celular.objects.filter(id=celular_id)
            tienda = getattr(venta, "tienda", None) if venta else None
            if tienda is not None and getattr(tienda, "id", None):
                qs = qs.filter(tienda_id=tienda.id)
            cel = qs.first()
        except Exception:
            cel = None
        eliminado = cel is None or not getattr(cel, "activo", True) or getattr(cel, "is_deleted", False)
        actualizado = False
        if not eliminado:
            snap_pv = item.get("precio_venta", item.get("costo_original"))
            try:
                if snap_pv is not None and Decimal(str(snap_pv)).quantize(Decimal("0.01")) != Decimal(str(cel.precio_venta)).quantize(Decimal("0.01")):
                    actualizado = True
            except Exception:
                pass
        return {
            "is_deleted": eliminado,
            "producto_activo": not eliminado,
            "producto_existe": not eliminado,
            "is_updated": actualizado,
            "updated_fields": ["precio_venta"] if actualizado else [],
        }
        """
        Asegura img_url/producto_imagen, is_deleted y is_updated actualizados.
        is_deleted y is_updated se recalculan contra estado actual del producto/inventario.
        Inventario/stock se excluye de is_updated por requerimiento.
        """
        if not productos_json:
            return productos_json
        # Mapas para fallback
        fallback_img = {}
        fallback_deleted = {}
        # Map pid -> (producto, inventario) para is_updated
        pid_to_current = {}
        tienda = getattr(venta, "tienda", None) if venta else None
        # Si tenemos venta_productos_qs, usar sus productos para mapas rápidos
        if venta_productos_qs is not None:
            for vp in venta_productos_qs:
                pid = vp.producto.id if vp.producto else None
                # imagen
                try:
                    if vp.producto and getattr(vp.producto, "imagen", None) and hasattr(vp.producto.imagen, "url") and vp.producto.imagen:
                        url = vp.producto.imagen.url
                        abs_url = request.build_absolute_uri(url) if request and url else url
                        if pid is not None:
                            fallback_img[pid] = abs_url
                    else:
                        if pid is not None and pid not in fallback_img:
                            fallback_img[pid] = None
                except Exception:
                    if pid is not None:
                        fallback_img[pid] = None
                # is_deleted
                try:
                    if pid is not None:
                        fallback_deleted[pid] = VentaService._is_deleted(vp.producto)
                except Exception:
                    continue
        # Preparar cache de actuales para is_updated (producto + inventario)
        # No hacer query por cada item si ya tenemos fallback; hacerlo lazy
        def get_current(pid):
            if pid in pid_to_current:
                return pid_to_current[pid]
            try:
                from apps.producto.models import Producto
                from apps.inventario.models import Inventario
                producto = Producto.objects.select_related("categoria").filter(id=pid).first()
                inventario = None
                if producto and tienda:
                    inventario = Inventario.objects.filter(producto_id=pid, tienda=tienda).first()
                    # si no hay inventario exacto, buscar cualquiera del producto
                    if not inventario:
                        inventario = Inventario.objects.filter(producto_id=pid).first()
                # también caso producto None (hard delete)
                if producto is None:
                    # intentar igual inventario por pid aunque producto no exista (huérfano)
                    if tienda:
                        inventario = Inventario.objects.filter(producto_id=pid, tienda=tienda).first()
                pid_to_current[pid] = (producto, inventario)
                return producto, inventario
            except Exception:
                pid_to_current[pid] = (None, None)
                return None, None

        enriched = []
        for item in productos_json:
            if not isinstance(item, dict):
                enriched.append(item)
                continue
            pid = item.get("producto_id")
            # --- item celular: no pasa por Producto/Inventario ---
            if item.get("celular_id") is not None and pid is None:
                item.update(VentaService._enriquecer_celular(item, item.get("celular_id"), venta))
                enriched.append(item)
                continue
            # --- img_url ---
            has_img = item.get("img_url") or item.get("producto_imagen")
            if not has_img:
                url = fallback_img.get(pid)
                # si fallback no tenía y tenemos producto actual, intentar sacar imagen de DB
                if url is None and pid is not None:
                    prod, _ = get_current(pid)
                    try:
                        if prod and getattr(prod, "imagen", None) and hasattr(prod.imagen, "url") and prod.imagen:
                            u = prod.imagen.url
                            url = request.build_absolute_uri(u) if request and u else u
                    except Exception:
                        url = None
                item["producto_imagen"] = url
                item["img_url"] = url
                item["imagen"] = url
            else:
                if not item.get("img_url") and item.get("producto_imagen"):
                    rel = item.get("producto_imagen")
                    try:
                        item["img_url"] = request.build_absolute_uri(rel) if request and rel and rel.startswith("/") else rel
                        item["imagen"] = item["img_url"]
                    except Exception:
                        pass
                if item.get("img_url") and not item.get("imagen"):
                    item["imagen"] = item["img_url"]

            # --- is_deleted ---
            live_deleted = fallback_deleted.get(pid)
            if live_deleted is None and pid is not None:
                try:
                    from apps.producto.models import Producto
                    p = Producto.objects.filter(id=pid).first()
                    if p is None:
                        live_deleted = True
                    else:
                        live_deleted = VentaService._is_deleted(p)
                except Exception:
                    live_deleted = None
            if live_deleted is not None:
                item["is_deleted"] = live_deleted
            elif "is_deleted" not in item:
                item["is_deleted"] = pid is None
            if "producto_activo" not in item or live_deleted is not None:
                item["producto_activo"] = not item["is_deleted"]
            if "producto_existe" not in item or live_deleted is not None:
                item["producto_existe"] = not item["is_deleted"]

            # --- is_updated (nombre, categoria, precio_venta, precio_compra) ---
            # No incluir cantidad/stock por requerimiento
            if item.get("is_deleted"):
                item["is_updated"] = False
                item["updated_fields"] = []
                prod_curr, inv_curr = (None, None)
            else:
                prod_curr, inv_curr = get_current(pid) if pid is not None else (None, None)
                # si snapshot viejo no tenía campos para comparar, _check_updated lo ignora
                is_upd, fields = VentaService._check_updated(item, prod_curr, inv_curr)
                item["is_updated"] = is_upd
                item["updated_fields"] = fields

            # --- categoria_data (backfill para ventas viejas sin snapshot) ---
            if not isinstance(item.get("categoria_data"), dict):
                if prod_curr is None and pid is not None and not item.get("is_deleted"):
                    prod_curr, _ = get_current(pid)
                cat_live = getattr(prod_curr, "categoria", None) if prod_curr is not None else None
                if cat_live is not None:
                    try:
                        cat_img = cat_live.imagen.url if getattr(cat_live, "imagen", None) and cat_live.imagen else None
                    except Exception:
                        cat_img = None
                    if cat_img and request is not None and cat_img.startswith("/"):
                        try:
                            cat_img = request.build_absolute_uri(cat_img)
                        except Exception:
                            pass
                    item["categoria_data"] = {
                        "categoria_id": cat_live.id,
                        "nombre": cat_live.nombre,
                        "descripcion": getattr(cat_live, "descripcion", None),
                        "color": getattr(cat_live, "color", None),
                        "imagen": cat_img,
                        "activo": getattr(cat_live, "activo", True),
                        "is_deleted": VentaService._is_categoria_deleted(cat_live),
                    }
                    if not item.get("categoria_color") and getattr(cat_live, "color", None):
                        item["categoria_color"] = cat_live.color
                else:
                    # sin objeto live: conservar snapshot plano existente
                    item["categoria_data"] = {
                        "categoria_id": item.get("categoria_id"),
                        "nombre": item.get("categoria_nombre") or "Sin categoría",
                        "descripcion": None,
                        "color": item.get("categoria_color"),
                        "imagen": None,
                        "activo": True,
                        "is_deleted": "(Delete)" in str(item.get("categoria_nombre") or ""),
                    }

            enriched.append(item)
        return enriched

    @staticmethod
    def build_item_sunat(calculo):
        codigo = calculo.get("codigo_sunat")
        if codigo is None and calculo.get("producto") is not None:
            codigo = calculo["producto"].sku
        descripcion = calculo.get("descripcion_sunat")
        if descripcion is None and calculo.get("producto") is not None:
            descripcion = calculo["producto"].nombre
        return {
            "codigo": codigo,
            "unidad": "NIU",
            "descripcion": descripcion,
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


import json as _json


def _parse_productos_json(productos_raw):
    """Normaliza productos_json a list[dict]. Acepta list o JSON string."""
    if not productos_raw:
        return []
    if isinstance(productos_raw, str):
        try:
            parsed = _json.loads(productos_raw)
        except Exception:
            return []
        productos_raw = parsed
    if not isinstance(productos_raw, list):
        return []
    return productos_raw


def _get_cantidad_safe(item):
    """Extrae cantidad como int positivo o None si inválido."""
    raw = item.get("cantidad", 0)
    try:
        c = int(raw)
    except (ValueError, TypeError):
        try:
            c = int(float(str(raw)))
        except Exception:
            return None
    if c <= 0:
        return None
    return c


def _get_precio_unitario_safe(item, cantidad):
    """
    Retorna precio_unitario (ya con descuento aplicado) como float.
    Replica la lógica histórica de SalesByDayMonthView/TopProductsByMonthView:
    - Si existe precio_unitario lo usa directo
    - Si no, intenta reconstruir: base (precio_venta/costo_original) - descuento/cantidad
    - Fallback valor_unitario*1.18 o valor_venta/cantidad*1.18
    """
    precio_raw = item.get("precio_unitario")
    if precio_raw is None:
        base = item.get("precio_venta")
        if base is None:
            base = item.get("costo_original")
        if base is not None:
            try:
                base_f = float(base)
            except Exception:
                try:
                    base_f = float(str(base).replace(",", "."))
                except Exception:
                    base_f = 0.0
            disc_raw = item.get("descuento")
            try:
                descuento = float(disc_raw) if disc_raw not in (None, "") else 0.0
            except Exception:
                descuento = 0.0
            if descuento and cantidad:
                precio_raw = base_f - (descuento / cantidad)
            else:
                precio_raw = base_f
        else:
            vu = item.get("valor_unitario")
            if vu is not None:
                try:
                    precio_raw = float(vu) * 1.18
                except Exception:
                    precio_raw = 0
            elif item.get("valor_venta") is not None and cantidad:
                try:
                    precio_raw = float(item.get("valor_venta")) / cantidad * 1.18
                except Exception:
                    precio_raw = 0
            else:
                precio_raw = 0

    try:
        precio = float(precio_raw)
    except (ValueError, TypeError):
        try:
            precio = float(str(precio_raw).replace(",", "."))
        except Exception:
            precio = 0.0
    return precio


def calcular_total_productos_json(productos_raw):
    """
    Suma productos_json restando descuentos: sum(precio_unitario * cantidad).
    precio_unitario ya viene con descuento prorrateado aplicado.
    """
    productos = _parse_productos_json(productos_raw)
    total = 0.0
    for item in productos:
        if not isinstance(item, dict):
            continue
        cantidad = _get_cantidad_safe(item)
        if cantidad is None:
            continue
        precio = _get_precio_unitario_safe(item, cantidad)
        total += round(precio * cantidad, 2)
    return round(total, 2)


def calcular_total_venta(venta):
    """
    Calcula el monto real de una venta usando productos_json.
    Fallback a venta.total si productos_json está vacío (compatibilidad histórica).
    """
    total = calcular_total_productos_json(getattr(venta, "productos_json", None))
    # Si productos_json vacío pero la venta tiene total >0, usar total como fallback
    if total == 0.0 and getattr(venta, "productos_json", None) in (None, [], "", {}):
        try:
            fallback = float(getattr(venta, "total", 0) or 0)
            return round(fallback, 2)
        except Exception:
            return 0.0
    return total


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
    def _build_logo_url(tienda):
        from django.conf import settings as django_settings
        from urllib.parse import urljoin

        domain = (getattr(django_settings, "DOMAIN", None) or "").rstrip("/")
        media_url = (getattr(django_settings, "MEDIA_URL", "/media/") or "/media/")
        logo = getattr(tienda, "logo_img", None)
        if not domain or not logo:
            return None
        relative = urljoin(media_url, logo.name)
        if not relative.startswith("/"):
            relative = "/" + relative
        return f"{domain}{relative}"

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
            "logo_url": SunatService._build_logo_url(tienda),
            "cliente": {
                "tipoDoc": venta.tipo_documento_cliente,
                "numDoc": venta.numero_documento_cliente,
                "nombre": venta.nombre_cliente,
            },
            "items": productos_items_for_sunat,
            "tipo_style_boleta_ticket": tienda.tipo_style_boleta_ticket,
            "tipo_style_boleta_pdf": tienda.tipo_style_boleta_pdf,
            "tipo_style_factura_pdf": tienda.tipo_style_factura_pdf,
            "emisor": {
                "claveSol": tienda.sol_password,
                "userSol": tienda.sol_user,
                "certPriv": tienda.cert_clave_privada,
                "certPublic": tienda.cert_clave_publica,
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
        import traceback
        import requests
        from .exceptions import SunatError
        from core.settings import SUNAT_API_KEY

        php_url = SunatService.get_php_url(tipo_comprobante)
        try:
            response = requests.post(
                php_url,
                json=comprobante_data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": SUNAT_API_KEY,
                },
                timeout=30,
            )
        except requests.exceptions.ConnectionError as e:
            print(f"[SUNAT][ERROR] No se pudo conectar al servidor de SUNAT: {e}")
            print(traceback.format_exc())
            raise SunatError("No se pudo conectar al servidor de SUNAT")
        except requests.exceptions.Timeout as e:
            print(f"[SUNAT][ERROR] Tiempo de espera agotado al conectar con SUNAT: {e}")
            print(traceback.format_exc())
            raise SunatError("Tiempo de espera agotado al conectar con SUNAT")
        except requests.exceptions.RequestException as e:
            print(f"[SUNAT][ERROR] Error de conexión con SUNAT: {e}")
            print(traceback.format_exc())
            raise SunatError(str(e))

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            err_detail = response.text.strip()

            print("\n[SUNAT][ERROR] El endpoint PHP respondió con un error HTTP:")
            print(f"[SUNAT][ERROR] Status code: {response.status_code}")
            print(f"[SUNAT][ERROR] URL: {php_url}")
            print(f"[SUNAT][ERROR] Cuerpo de la respuesta: {response.text}")
            print(f"[SUNAT][ERROR] Detalle excepción: {e}")
            print("==========================================")

            raise SunatError(f"El endpoint PHP devolvió el error HTTP {response.status_code}: {err_detail}")

        try:
            return response.json()
        except ValueError:
            # Tolerancia: si el PHP emitió avisos antes del JSON, recortar desde el primer "{".
            texto = response.text or ""
            inicio = texto.find("{")
            if inicio != -1:
                try:
                    import json as _json

                    return _json.loads(texto[inicio:])
                except ValueError:
                    pass
            print("\n[SUNAT][ERROR] Respuesta inválida (no es JSON) del servidor de SUNAT:")
            print(f"[SUNAT][ERROR] HTTP {response.status_code} | Body: {response.text}")
            print("==========================================")
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
