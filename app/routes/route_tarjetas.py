from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from app.controllers import ctrl_tarjetas
from app.core.cfg_auth import get_cliente
from app.core.cfg_database import get_db
from app.schemas.sch_tarjetas import (
    CompraDeudaRequest,
    DisposicionEfectivoRequest,
    ConfiguracionSeguridadRequest
)

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"], dependencies=[Depends(get_cliente)])

@router.post("/compra-deuda")
def compra_deuda(
    body: CompraDeudaRequest,
    conn: Connection = Depends(get_db),
    cliente: dict = Depends(get_cliente),
):
    return ctrl_tarjetas.consolidacion_deuda(
        conn,
        cliente["pkcliente"],
        body.banco_origen,
        body.tipo_tarjeta,
        body.cci_pago,
        body.monto_consolidar,
        body.plazo_meses
    )

@router.post("/disposicion-efectivo")
def disposicion_efectivo(
    body: DisposicionEfectivoRequest,
    conn: Connection = Depends(get_db),
    cliente: dict = Depends(get_cliente),
):
    return ctrl_tarjetas.disposicion_efectivo(
        conn,
        cliente["pkcliente"],
        body.codcuentacredito,
        body.monto_retiro,
        body.linea_credito_total
    )

@router.post("/configuracion-seguridad")
def configuracion_seguridad(
    body: ConfiguracionSeguridadRequest,
    conn: Connection = Depends(get_db),
    cliente: dict = Depends(get_cliente),
):
    return ctrl_tarjetas.actualizar_configuracion_seguridad(
        conn,
        cliente["pkcliente"],
        body.codcuentacredito,
        body.compras_internet,
        body.compras_exterior,
        body.disposicion_efectivo,
        body.sobregiro
    )
