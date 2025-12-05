
from decimal import Decimal

from django.shortcuts import get_object_or_404
from apps import comprobante
from apps.comprobante.models import ComprobanteElectronico
from apps.inventario.models import Inventario
from core.settings import SUNAT_PHP
import requests
class SunatOperations():
    
    headers = {"Content-Type": "application/json"}    
    boletaURL = SUNAT_PHP + "/src/api/boleta-post.php"
    facturaURL = SUNAT_PHP + "/src/api/factura-post.php"
    comprobante = None
    comprobanteBuild = None
    tipoComprobante = "Boleta"
    responseSunat = None
    newSerie  =None
    newCorrelativo = None
    productos_items =[]
    cliente = {
        "numero":None,
        "nombre_o_razon_social":None,
        "nombre_completo":None
        
    }
    isSuccessSunat =False
    leyenda = ""
    subtotal = Decimal(0)
    gravado_total = Decimal(0)
    igv_total = Decimal(0)
    total = Decimal(0)
    descuento_total = Decimal(0)
    exonerado_total = Decimal(0) 
    porcentaje_igv = Decimal("18.00") 
    factor_igv = porcentaje_igv / Decimal("100.00") 
    def __init__(self,tipoComprobante):
         self.tipoComprobante = tipoComprobante
    
    def buildComprobante(self):
        self.comprobanteBuild = {
                        "serie": self.newSerie,
                        "correlativo": self.newCorrelativo,
                        "moneda": "PEN",
                        "gravadas": float(self.gravado_total), # type: ignore
                        "exoneradas": float(self.exonerado_total), # type: ignore
                        "igv": float(self.igv_total), # type: ignore
                        "valorVenta": float(self.subtotal), # type: ignore
                        "subTotal": float(self.subtotal + self.igv_total), # type: ignore
                        "total": float(self.total), # type: ignore
                        "leyenda": self.leyenda,
                        "cliente": self.cliente,
                        "items":self.productos_items
                }
    def sendSunatComprobante(self):
        try:
            response = requests.post(self.facturaURL if self.tipoComprobante == "Factura" else self.boletaURL , json=self.comprobanteBuild, headers=self.headers)           
            self.responseSunat  = response.json()
            self.isSuccessSunat =True
        except Exception:
            self.isSuccessSunat =False
            raise Exception(f"La API PHP devolvió una respuesta no JSON: {response.text}") # type: ignore
            

    def makeCliente(self,numero,nombre):
         self.cliente = {
                    "tipoDoc": "6" if self.tipoComprobante == "Factura" else "1",
                    "numDoc":  numero,# type: ignore
                    "nombre": nombre
                }
    def saveComprobante(self,venta):
        
        ComprobanteElectronico.objects.create(
                venta=venta,
                tipo_comprobante=self.data["tipoComprobante"], # type: ignore
                serie=self.comprobante["serie"], # type: ignore
                correlativo=self.comprobante["correlativo"], # type: ignore
                moneda=self.comprobante["moneda"], # type: ignore
                gravadas=Decimal(self.comprobante["gravadas"]), # type: ignore
                igv=Decimal(self.comprobante["igv"]), # type: ignore
                valorVenta=Decimal(self.comprobante["valorVenta"]), # type: ignore
                sub_total=Decimal(self.omprobante["subTotal"]), # type: ignore
                total=Decimal(self.comprobante["total"]), # type: ignore
                leyenda=self.comprobante["leyenda"], # type: ignore
                tipo_documento_cliente=self.comprobante["cliente"]["tipoDoc"], # type: ignore
                numero_documento_cliente=self.comprobante_["cliente"]["numDoc"], # type: ignore
                nombre_cliente=self.comprobante["cliente"]["nombre"], # type: ignore
                estado_sunat="Aceptado" if responseSunat["cdr_codigo"] == "0" else "Rechazado", # type: ignore
                xml_url=self.responseSunat.get("xml_url"), # type: ignore
                pdf_url=self-responseSunat.get("pdf_url"), # type: ignore
                cdr_url=self.responseSunat.get("cdr_url"), # type: ignore
                ticket_url=self.responseSunat.get("ticket_url"), # type: ignore
                items=self.comprobante["items"] # type: ignore
                ).save()
        
    def generateLeyenda(self):
        self.leyenda.generateLeyend(self.total) # type: ignore
             
    def prepareProductsForSunat(self,productosInventario):
          for item in productosInventario:
                    inventario = get_object_or_404(Inventario, id=item["inventarioId"])
                    producto = inventario.producto
                    cantidad = int(item["cantidad_final"])
                    descuento = Decimal(item["descuento"])
                    precio_base = Decimal(inventario.costo_venta) # type: ignore
                    # Descuento prorrateado por unidad
                    descuento_unitario = descuento / cantidad
                    # Precio final con IGV incluido
                    precio_unitario = precio_base - descuento_unitario
                    precio_unitario_original = precio_base
                    # Valor unitario sin IGV
                    valor_unitario = precio_unitario / (Decimal("1.00") + self.factor_igv)
                    # Cálculos finales
                    valor_venta = cantidad * valor_unitario
                    igv = valor_venta * self.factor_igv 
                    self.gravado_total += valor_venta
                    self.igv_total += igv
                    self.total += precio_unitario * cantidad
                    igv_calculado = valor_venta * self.factor_igv
                    self.productos_items.append({
                        "codigo": producto.sku,
                        "unidad": "NIU",
                        "descripcion": producto.nombre,
                        "cantidad": cantidad,
                        "valorUnitario": round(float(valor_unitario), 2),
                        "valorVenta": round(float(valor_venta), 2),
                        "baseIgv": round(float(valor_venta), 2),
                        "porcentajeIgv": 18,
                        "igv": round(float(igv_calculado), 2),
                        "tipoAfectacionIgv": "10",
                        "totalImpuestos": round(float(igv_calculado), 2),
                        "precioUnitario": round(float(precio_unitario), 2),
                        "costo_original": round(float(precio_unitario_original), 2),
                        "descuento": float(descuento)
                    })
           
    def generateSerieAndCorrelativo(self,correlativo_inicial_f = 2,correlativo_inicial_b = 1):
        tipo = self.tipoComprobante.lower() # type: ignore
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
                self.newSerie = f"{serie_base[0]}{str(int(serie_actual[1:]) + 1).zfill(3)}" # type: ignore
                self.newCorrelativo = "00000001"
            else:
                self.newSerie = serie_actual
                self.newCorrelativo = str(correlativo_actual + 1).zfill(8)
        else:
                self.newSerie = serie_base
                self.newCorrelativo = str(correlativo_inicial).zfill(8)
        
    def getDataComprobante(self):
          return  {
                        "tipo_comprobante": self.tipoComprobante, # type: ignore
                        "serie": comprobante.serie, # type: ignore
                        "correlativo": comprobante.correlativo, # type: ignore
                        "moneda": comprobante.moneda, # type: ignore
                        "gravadas": float(comprobante.gravadas), # type: ignore
                        "igv": float(comprobante.igv), # type: ignore
                        "valorVenta": float(comprobante.valorVenta), # type: ignore
                        "sub_total": float(comprobante.sub_total), # type: ignore
                        "total": float(comprobante.total), # type: ignore
                        "leyenda": comprobante.leyenda, # type: ignore
                        "tipo_documento_cliente": comprobante.tipo_documento_cliente, # type: ignore
                        "numero_documento_cliente": comprobante.numero_documento_cliente, # type: ignore
                        "nombre_cliente": comprobante.nombre_cliente, # type: ignore
                        "estado_sunat": comprobante.estado_sunat, # type: ignore
                        "xml_url": comprobante.xml_url, # type: ignore
                        "pdf_url": comprobante.pdf_url, # type: ignore
                        "cdr_url": comprobante.cdr_url, # type: ignore
                        "ticket_url": necomprobante.ticket_url, # type: ignore
                        "items": comprobante.items # type: ignore
                    }
        