"""Router de créditos (solicitar). Exige get_cliente."""
from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from app.controllers import ctrl_creditos
from app.core.cfg_auth import get_cliente
from app.core.cfg_database import get_db
from app.schemas.sch_creditos import (
    SolicitudCreditoRequest, 
    SolicitudCreditoResponse,
    SimularCreditoRequest,
    SimularCreditoResponse
)

router = APIRouter(prefix="/creditos", tags=["creditos"], dependencies=[Depends(get_cliente)])


@router.post("/solicitar", response_model=SolicitudCreditoResponse)
def solicitar(
    body: SolicitudCreditoRequest,
    conn: Connection = Depends(get_db),
    cliente: dict = Depends(get_cliente),
):
    return ctrl_creditos.solicitar(
        conn,
        cliente["pkcliente"],
        body.montosolicitud,
        body.plazo,
        body.codtipocredito,
        body.codactividadeconomica,
        body.montoingresoneto,
    )

@router.post("/simular", response_model=SimularCreditoResponse)
def simular(body: SimularCreditoRequest):
    return ctrl_creditos.simular_credito(
        monto=body.monto,
        tea=body.tea,
        plazo=body.plazo,
        tipo_desgravamen=body.tipo_desgravamen,
        seguro_vida_tranki=body.seguro_vida_tranki,
        es_convenio=body.es_convenio
    )
