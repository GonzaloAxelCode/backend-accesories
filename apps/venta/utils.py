from datetime import date, datetime
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware

from num2words import num2words

from apps.comprobante.models import ComprobanteElectronico, NotaCreditoDB  
def normalize_date(value, end_of_day=False):
    if isinstance(value, str):
        d = parse_date(value)
    elif isinstance(value, (list, tuple)):
        year, month, day = value
        d = date(year, month + 1, day)
    elif isinstance(value, date):
        d = value
    else:
        return None

    if not d:
        return None

    dt = datetime.combine(d, datetime.max.time() if end_of_day else datetime.min.time())
    return make_aware(dt)

def generateLeyend(monto):
    return f"SON {num2words(monto, lang='es').upper()} CON 00/100 SOLES"


def getNextCorrelativo_ORIGINAL(tipo_comprobante: str,correlativo_inicial_f: int = 10,correlativo_inicial_b: int =15,correlativo_inicial_n: int = 4):
                tipo = tipo_comprobante.lower()
                if tipo == "factura":
                    serie_base = "F001"
                    correlativo_inicial = correlativo_inicial_f
                else:
                    serie_base = "B001"
                    correlativo_inicial = correlativo_inicial_b

                ultimo = (
                    ComprobanteElectronico.objects
                    .filter(serie__startswith=serie_base)
                    .order_by('-serie', '-correlativo')
                    .first()
                )

                if ultimo:
                    serie_actual = ultimo.serie
                    correlativo_actual = int(ultimo.correlativo) # type: ignore

                    if correlativo_actual >= 99999999:
                        nueva_serie = f"{serie_base[0]}{str(int(serie_actual[1:]) + 1).zfill(3)}" # type: ignore
                        nuevo_correlativo = "00000001"
                    else:
                        nueva_serie = serie_actual
                        nuevo_correlativo = str(correlativo_actual + 1).zfill(8)

                else:
                    nueva_serie = serie_base
                    nuevo_correlativo = str(correlativo_inicial).zfill(8)

                return nueva_serie, nuevo_correlativo


def getNextCorrelativo(
    tipo_comprobante: str,
    serie_base: str | None = None,
    correlativo_inicial_f: int = 10,
    correlativo_inicial_b: int = 15,
    correlativo_inicial_n: int = 4,
):
    tipo = tipo_comprobante.lower()

    # 🔹 FACTURA
    if tipo in ["factura", "01"]:
        serie_base = "F001"
        correlativo_inicial = correlativo_inicial_f

    # 🔹 BOLETA
    elif tipo in ["boleta", "03"]:
        serie_base = "B001"
        correlativo_inicial = correlativo_inicial_b

    # 🔹 NOTA DE CRÉDITO (07)
    elif tipo in ["nota_credito", "07"]:
        if not serie_base:
            raise ValueError("Para nota de crédito se requiere la serie base (B001 o F001)")
        correlativo_inicial = correlativo_inicial_n

    else:
        raise ValueError("Tipo de comprobante no soportado")

    ultimo = (
        ComprobanteElectronico.objects
        .filter(serie=serie_base, tipo_comprobante="07")
        .order_by("-correlativo")
        .first()
    )

    if ultimo:
        nuevo_correlativo = str(int(ultimo.correlativo) + 1).zfill(8) # type: ignore
    else:
        nuevo_correlativo = str(correlativo_inicial).zfill(8)

    return serie_base, nuevo_correlativo

def getNextCorrelativoNotaCredito(
    tipo_comprobante_modifica: str,
    correlativo_inicial: int = 6
):
    tipo = tipo_comprobante_modifica.lower()

    if tipo == "factura":
        serie_base = "F001"
    elif tipo == "boleta":
        serie_base = "B001"
    elif tipo == "anonima":
        serie_base = "B001"
    else:
        raise ValueError("Tipo de comprobante inválido")

    ultimo = (
        NotaCreditoDB.objects
        .filter(serie=serie_base)
        .order_by('-correlativo')
        .first()
    )

    if ultimo:
        correlativo_actual = int(ultimo.correlativo)

        if correlativo_actual >= 99999999:
            raise ValueError(
                f"Correlativo máximo alcanzado para la serie {serie_base}"
            )

        nueva_serie = serie_base
        nuevo_correlativo = str(correlativo_actual + 1).zfill(8)

    else:
        nueva_serie = serie_base
        nuevo_correlativo = str(correlativo_inicial).zfill(8)

    return nueva_serie, nuevo_correlativo


def getNextCorrelativoNotaCreditoMultitienda(
    tipo_comprobante_modifica: str,
    tienda
):
    tipo = tipo_comprobante_modifica.lower()

    # ============================
    # FORMAR SERIE
    # ============================
    numero_serie = tienda.serie or "001"

    if tipo == "factura":
        serie_base = f"F{numero_serie}"   # Nota crédito de factura
    elif tipo in ["boleta", "anonima"]:
        serie_base = f"B{numero_serie}"   # Nota crédito de boleta
    else:
        raise ValueError("Tipo de comprobante inválido")

    # ============================
    # CORRELATIVO INICIAL DESDE TIENDA
    # ============================
    correlativo_inicial = tienda.correlativo_inicial_nota_credito or 1

    # ============================
    # BUSCAR ÚLTIMO
    # ============================
    ultimo = (
        NotaCreditoDB.objects
        .filter(venta__tienda=tienda, serie=serie_base)
        .order_by('-correlativo')
        .first()
    )

    # ============================
    # GENERAR CORRELATIVO
    # ============================
    if ultimo:
        correlativo_actual = int(ultimo.correlativo)

        if correlativo_actual >= 99999999:
            raise ValueError(
                f"Correlativo máximo alcanzado para la serie {serie_base}"
            )

        nuevo_correlativo = str(correlativo_actual + 1).zfill(8)
    else:
        nuevo_correlativo = str(correlativo_inicial).zfill(8)

    return serie_base, nuevo_correlativo


def getNextCorrelativoMultiTienda(tipo_comprobante: str, tienda):
    tipo = tipo_comprobante.lower()

    # ============================
    # FORMAR SERIE COMPLETA
    # ============================
    numero_serie = tienda.serie or "001"

    if tipo == "factura":
        serie_base = f"F{numero_serie}"
        correlativo_inicial = tienda.correlativo_inicial_factura or 1
    else:
        serie_base = f"B{numero_serie}"
        correlativo_inicial = tienda.correlativo_inicial_boleta or 1

    # ============================
    # BUSCAR ÚLTIMO
    # ============================
    ultimo = (
        ComprobanteElectronico.objects
        .filter(venta__tienda=tienda, serie=serie_base)
        .order_by('-correlativo')
        .first()
    )

    # ============================
    # GENERAR CORRELATIVO
    # ============================
    if ultimo:
        correlativo_actual = int(ultimo.correlativo) # type: ignore
        nuevo_correlativo = str(correlativo_actual + 1).zfill(8)
    else:
        nuevo_correlativo = str(correlativo_inicial).zfill(8)

    return serie_base, nuevo_correlativo