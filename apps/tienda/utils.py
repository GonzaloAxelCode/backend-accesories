from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone


PERIODO_PLAN_DIAS = 30


def get_personal_contable(tienda):
    """Personal que cuenta para el límite del plan: todos los usuarios de
    la tienda excepto su propietario (rol admin_tienda, no consume cupo)."""
    qs = tienda.users_tienda.all()
    if tienda.propietario_id:
        qs = qs.exclude(pk=tienda.propietario_id)
    return qs


def get_periodo_plan(tienda):
    """Ventana de 30 días corridos desde el inicio del plan vigente."""
    inicio = tienda.plan_desde or tienda.date_created or timezone.now()
    fin = inicio + timedelta(days=PERIODO_PLAN_DIAS)
    return inicio, fin


def get_uso_periodo(tienda):
    """Cuenta boletas/facturas emitidas en vivo dentro del periodo del plan.

    Base: ComprobanteElectronico con fecha_emision dentro de
    [plan_desde, plan_desde + 30 días). Se cuenta desde comprobantes (no
    desde ventas) porque hay ventas PENDIENTE legacy que nunca generaron
    comprobante. Se excluyen comprobantes RECHAZADOS y los de ventas
    ANULADAS. No bloquea emisiones, solo informa uso vs. límite.
    """
    from apps.comprobante.models import ComprobanteElectronico

    inicio, fin = get_periodo_plan(tienda)
    ahora = timezone.now()
    vencido = ahora >= fin

    base = (
        ComprobanteElectronico.objects.filter(
            venta__tienda=tienda,
            venta__activo=True,
            fecha_emision__gte=inicio,
            fecha_emision__lt=fin,
        )
        .exclude(estado_sunat__iexact="RECHAZADO")
        .exclude(venta__estado__iexact="ANULADA")
    )

    stats = base.aggregate(
        boletas=Count("pk", filter=Q(tipo_comprobante__iexact="boleta")),
        facturas=Count("pk", filter=Q(tipo_comprobante__iexact="factura")),
    )
    boletas = stats["boletas"] or 0
    facturas = stats["facturas"] or 0

    return {
        "inicio": inicio,
        "fin": fin,
        "vencido": vencido,
        "boletas_emitidas": boletas,
        "facturas_emitidas": facturas,
        "dias_restantes": max(0, (fin - ahora).days) if not vencido else 0,
    }


def get_estado_limites(tienda):
    """Uso vs. límites del plan + flags de bloqueo.

    Incluye todo lo de get_uso_periodo más: límites, num_personal,
    excede_boletas/facturas/personal y bloqueado_productos (se bloquea
    crear productos si cualquiera de los dos límites de comprobantes se
    alcanzó, pues no existe limite_productos en el plan).

    Reglas:
    - Sin plan asignado: no bloquea (fail-open, con sin_plan=True para
      que el frontend pida asignar uno).
    - Límite 0 = 0 permitido (fail-closed).
    - El propietario (admin_tienda) no cuenta como personal del plan.
    - El bypass de superuser se aplica en cada vista, no aquí.
    """
    from apps.producto.models import Producto

    uso = get_uso_periodo(tienda)
    num_personal = get_personal_contable(tienda).count()
    num_productos = Producto.objects.filter(tienda=tienda, activo=True).count()
    plan = tienda.plan

    estado = dict(uso)
    estado["num_personal"] = num_personal
    estado["num_productos"] = num_productos

    if plan is None:
        estado.update({
            "sin_plan": True,
            "limite_boletas": None,
            "limite_facturas": None,
            "limite_personal": None,
            "limite_productos": None,
            "excede_boletas": False,
            "excede_facturas": False,
            "excede_personal": False,
            "excede_productos": False,
            "bloqueado_productos": False,
        })
        return estado

    excede_boletas = uso["boletas_emitidas"] >= plan.limite_boletas
    excede_facturas = uso["facturas_emitidas"] >= plan.limite_facturas
    excede_personal = num_personal >= plan.limite_personal
    excede_productos = num_productos >= plan.limite_productos

    estado.update({
        "sin_plan": False,
        "limite_boletas": plan.limite_boletas,
        "limite_facturas": plan.limite_facturas,
        "limite_personal": plan.limite_personal,
        "limite_productos": plan.limite_productos,
        "excede_boletas": excede_boletas,
        "excede_facturas": excede_facturas,
        "excede_personal": excede_personal,
        "excede_productos": excede_productos,
        "bloqueado_productos": excede_productos,
    })
    return estado


def renovar_si_vencido(tienda):
    """Detecta periodo vencido y lo renueva automáticamente.

    - Guarda snapshot del periodo terminado en HistorialPeriodoPlan
      (idempotente por unique tienda+inicio: no duplica).
    - Avanza plan_desde de a bloques de PERIODO_PLAN_DIAS hasta cubrir
      hoy (mantiene el día de corte original aunque pasen meses inactivo).
    - Resetea UsoMensualTienda del mes calendario a 0 (compatibilidad).
    - Retorna dict con renovado, periodos_saltados, inicio y fin vigentes.
    - Sin plan asignado no hay periodo que renovar: retorna renovado=False.
    """
    from datetime import date

    from apps.tienda.models import HistorialPeriodoPlan, UsoMensualTienda

    if tienda.plan_id is None:
        inicio, fin = get_periodo_plan(tienda)
        return {
            "renovado": False,
            "periodos_saltados": 0,
            "inicio": inicio,
            "fin": fin,
        }

    ahora = timezone.now()
    inicio, fin = get_periodo_plan(tienda)
    if ahora < fin:
        return {
            "renovado": False,
            "periodos_saltados": 0,
            "inicio": inicio,
            "fin": fin,
        }

    # Snapshot del periodo que terminó (conteo en vivo de esa ventana)
    uso = get_uso_periodo(tienda)
    HistorialPeriodoPlan.objects.get_or_create(
        tienda=tienda,
        inicio=uso["inicio"],
        defaults={
            "plan": tienda.plan,
            "fin": uso["fin"],
            "boletas_emitidas": uso["boletas_emitidas"],
            "facturas_emitidas": uso["facturas_emitidas"],
        },
    )

    # Avanzar el corte por periodos completos hasta vigencia
    periodos_saltados = 0
    while ahora >= fin:
        inicio = inicio + timedelta(days=PERIODO_PLAN_DIAS)
        fin = inicio + timedelta(days=PERIODO_PLAN_DIAS)
        periodos_saltados += 1

    tienda.plan_desde = inicio
    tienda.save(update_fields=["plan_desde"])

    mes_actual = date.today().replace(day=1)
    UsoMensualTienda.objects.update_or_create(
        tienda=tienda,
        mes=mes_actual,
        defaults={"boletas_emitidas": 0, "facturas_emitidas": 0},
    )

    return {
        "renovado": True,
        "periodos_saltados": periodos_saltados,
        "inicio": inicio,
        "fin": fin,
    }
