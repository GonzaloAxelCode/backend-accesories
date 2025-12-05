from datetime import date, datetime
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware

from num2words import num2words

from apps.comprobante.models import ComprobanteElectronico  
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


def getNextCorrelativo(tipo_comprobante: str,correlativo_inicial_f: int = 2,correlativo_inicial_b: int = 1):
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