from pydantic import BaseModel, Field
from decimal import Decimal

class ClienteCrearRequest(BaseModel):
    nomcliente: str = Field(..., description="Nombres y Apellidos del cliente (ej. Pérez, Juan)")
    numerodocumentoidentidad: str = Field(..., min_length=8, max_length=12, description="Número de documento de identidad (DNI o RUC)")
    email: str = Field(..., description="Correo electrónico")
    numerotelefonopersonal: str = Field(..., description="Número de teléfono celular")
    montoingresoneto: Decimal = Field(..., ge=0, description="Monto de ingreso neto mensual")
    codactividadeconomica: str = Field("4711", description="Código de actividad económica CIIU (default 4711)")
    codubigeo: str = Field("120101", description="Código ubigeo (default 120101 - Huancayo)")


class GestionCobranzaRequest(BaseModel):
    pkcuentacredito: int
    codtipogestion: str = Field(..., description="SMS, LLAM, VISI, CART, COMP, JUDI")
    resultado: str
    compromisopago: str | None = Field(None, description="Fecha en formato YYYY-MM-DD")
    montocomprometido: Decimal | None = Field(None, ge=0)


class TransicionMoraRequest(BaseModel):
    pkcuentacredito: int
    nuevo_estado: str = Field(..., description="JUDICIAL o CASTIGO")

