from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional

class CompraDeudaRequest(BaseModel):
    banco_origen: str
    tipo_tarjeta: str
    cci_pago: str = Field(..., min_length=20, max_length=20)
    monto_consolidar: Decimal = Field(..., gt=0)
    plazo_meses: int = Field(..., ge=12, le=36)

class DisposicionEfectivoRequest(BaseModel):
    codcuentacredito: str
    monto_retiro: Decimal = Field(..., gt=0)
    linea_credito_total: Decimal = Field(..., gt=0)

class ConfiguracionSeguridadRequest(BaseModel):
    codcuentacredito: str
    compras_internet: Optional[str] = Field(None, pattern="^[SN]$")
    compras_exterior: Optional[str] = Field(None, pattern="^[SN]$")
    disposicion_efectivo: Optional[str] = Field(None, pattern="^[SN]$")
    sobregiro: Optional[str] = Field(None, pattern="^[SN]$")
