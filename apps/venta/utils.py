from datetime import date, datetime
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware

def normalize_date(value, end_of_day=False):
    """
    Convierte fechas que vienen como string "2025-01-01" o array [2025,0,1]
    en datetime con zona horaria activa.
    """
    if isinstance(value, str):
        d = parse_date(value)
    elif isinstance(value, (list, tuple)):
        # Ojo: en JS los meses empiezan en 0, en Python en 1
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
