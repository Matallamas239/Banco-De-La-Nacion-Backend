"""Controlador de créditos: solicitar crédito (ME/CO)."""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.engine import Connection

from app.repositories import repo_creditos


def solicitar(
    conn: Connection,
    pkcliente: int,
    montosolicitud: Decimal,
    plazo: int,
    codtipocredito: str,
    codactividadeconomica: str,
    montoingresoneto: Decimal,
) -> dict:
    if codtipocredito not in repo_creditos.MAPA_TIPO_CREDITO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de crédito fuera de alcance (solo ME o CO)",
        )
    try:
        res = repo_creditos.crear_solicitud(
            conn,
            pkcliente=pkcliente,
            montosolicitud=montosolicitud,
            plazo=plazo,
            codtipocredito=codtipocredito,
            codactividadeconomica=codactividadeconomica,
            montoingresoneto=montoingresoneto,
        )
    except ValueError as e:
        if isinstance(e, repo_creditos.SemaforoRojoException):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Evaluación de Elegibilidad Fallida: Semáforo ROJO",
                    "elegibilidad": {
                        "motivo": str(e),
                        "reglas": [
                            {
                                "nombre": "Ratio Deuda-Ingreso (RDS)",
                                "limite": "Máximo 40.0%",
                                "actual": f"{e.rds:.1f}%",
                                "cumple": e.rds_ok,
                                "tipo": "rds",
                                "monto_maximo_sugerido": round(e.monto_max, 2),
                                "ingreso_minimo_sugerido": round(e.ingreso_min, 2),
                            },
                            {
                                "nombre": "Calificación crediticia SBS",
                                "limite": "Normal o CPP",
                                "actual": e.sbs_label,
                                "cumple": e.sbs_ok,
                                "tipo": "sbs",
                            },
                        ],
                    },
                },
            )
        if "Semáforo ROJO" in str(e):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "mensaje": "Solicitud registrada (En Evaluación)",
        "estado": "En Evaluación",
        "montosolicitud": montosolicitud,
        "plazo": plazo,
        **res,
    }


def simular_credito(
    monto: Decimal,
    tea: Decimal,
    plazo: int,
    tipo_desgravamen: str = "estandar",
    seguro_vida_tranki: bool = False,
    es_convenio: bool = False,
) -> dict:
    """
    Simula la cuota mensual de un crédito bajo el método francés,
    aplicando seguro de desgravamen, comisiones e ITF.
    """
    # Tasa efectiva mensual
    tea_float = float(tea) / 100
    im = (1 + tea_float) ** (30 / 360) - 1
    im_dec = Decimal(str(im))

    # Tasa de desgravamen
    id_tasa = Decimal("0")
    if tipo_desgravamen == "estandar":
        id_tasa = Decimal("0.000738")  # 0.0738% mensual
    elif tipo_desgravamen == "rescate":
        id_tasa = Decimal("0.00175")   # 0.175% mensual

    monto_financiar = Decimal(monto)
    
    # Seguro Vida Tranki
    if seguro_vida_tranki:
        t_vt = Decimal("0.0000148")  # 0.00148%
        dias_totales = plazo * 30
        prima_vt = monto_financiar * Decimal(dias_totales) * t_vt
        monto_financiar += prima_vt

    # Comisión por planilla
    cp = Decimal("5.00") if es_convenio else Decimal("0.00")

    # Cuota pura (Interés + Amortización)
    if im > 0 and plazo > 0:
        factor = (1 + im) ** -plazo
        cuota_pura_float = (float(monto_financiar) * im) / (1 - factor)
    else:
        cuota_pura_float = float(monto_financiar) / plazo if plazo > 0 else 0
        
    cuota_pura = Decimal(str(cuota_pura_float))

    # Seguro Desgravamen
    sd = monto_financiar * id_tasa

    # Subtotal para calcular ITF
    subtotal = cuota_pura + sd + cp
    itf = subtotal * Decimal("0.00005")

    cuota_total = subtotal + itf

    return {
        "monto_financiar": round(monto_financiar, 2),
        "cuota_pura": round(cuota_pura, 2),
        "seguro_desgravamen": round(sd, 2),
        "comision_planilla": round(cp, 2),
        "itf": round(itf, 2),
        "cuota_total": round(cuota_total, 2),
    }
