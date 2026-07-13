class VentaError(Exception):
    pass


class StockInsuficienteError(VentaError):
    def __init__(self, errores):
        self.errores = errores
        super().__init__("; ".join(errores))


class InventarioNoEncontradoError(VentaError):
    def __init__(self, inventario_id):
        self.inventario_id = inventario_id
        super().__init__(f"Inventario con id '{inventario_id}' no encontrado")


class DatosInvalidosError(VentaError):
    def __init__(self, campo, detalle=""):
        self.campo = campo
        super().__init__(f"Campo '{campo}' inválido{': ' + detalle if detalle else ''}")


class SunatError(VentaError):
    def __init__(self, detalle=""):
        super().__init__(f"Error con SUNAT{': ' + detalle if detalle else ''}")


class SunatRechazadoError(SunatError):
    def __init__(self, cdr_codigo, mensaje=""):
        self.cdr_codigo = cdr_codigo
        super().__init__(f"SUNAT rechazó el comprobante (código: {cdr_codigo}){': ' + mensaje if mensaje else ''}")
