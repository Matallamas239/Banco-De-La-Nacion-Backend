"""Schemas pydantic para solicitud de crédito."""
from __future__ import annotations
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SolicitudCreditoRequest(BaseModel):
    montosolicitud: Decimal = Field(..., gt=0)
    plazo: int = Field(..., gt=0, description="Número de cuotas / meses")
    codtipocredito: Literal["ME", "CO"] = Field(..., description="ME=Microempresa, CO=Consumo")
    codactividadeconomica: str
    montoingresoneto: Decimal = Field(..., ge=0)
    pkcliente: int | None = Field(None, description="PK del cliente (solo para admin/asesor)")
    con_seguro: bool = Field(True, description="Indica si tiene seguro de desgravamen (True=40.92%, False=43.92%)")
    fecha_desembolso: str | None = Field(None, description="Fecha de desembolso (YYYY-MM-DD), default hoy")
    dia_pago: int | None = Field(None, ge=1, le=31, description="Día del mes para pago de cuotas")


class SolicitudCreditoResponse(BaseModel):
    mensaje: str
    pksolicitud: int
    codsolicitud: str
    estado: str
    montosolicitud: Decimal
    plazo: int
