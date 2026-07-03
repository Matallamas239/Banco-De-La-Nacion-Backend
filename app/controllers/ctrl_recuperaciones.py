"""Controlador de recuperaciones (MPR - Cobranza/Mora)."""
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.engine import Connection
from sqlalchemy import text

from app.repositories import repo_recuperaciones
from app.repositories.repo_cuentas import PERIODO_CARTERA

def stats(conn: Connection) -> dict:
    return repo_recuperaciones.get_recuperaciones_stats(conn)

def listar_cartera(conn: Connection, banda: str) -> list[dict]:
    return repo_recuperaciones.listar_cartera_mora(conn, banda)

def registrar_gestion(
    conn: Connection,
    pkcuentacredito: int,
    codtipogestion: str,
    resultado: str,
    compromisopago: str | None,
    montocomprometido: Decimal | None,
    gestor: str
) -> dict:
    try:
        return repo_recuperaciones.registrar_gestion_cobranza(
            conn, pkcuentacredito, codtipogestion, resultado, compromisopago, montocomprometido, gestor
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

def historial(conn: Connection, pkcuentacredito: int) -> list[dict]:
    return repo_recuperaciones.listar_historial_cobranza(conn, pkcuentacredito)

def transicionar(conn: Connection, pkcuentacredito: int, nuevo_estado: str, cargo: str) -> dict:
    # 1. Obtener días de atraso del crédito
    row = conn.execute(
        text("""
            SELECT diasatrasocredito 
            FROM fagcuentacredito 
            WHERE pkcuentacredito = :pk AND periodomes = :periodo
        """),
        {"pk": pkcuentacredito, "periodo": PERIODO_CARTERA}
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Crédito no encontrado en la cartera actual.")

    dias_atraso = row["diasatrasocredito"]

    # 2. Validar umbrales y permisos por cargo
    nuevo_estado_upper = nuevo_estado.upper()
    if nuevo_estado_upper == 'JUDICIAL':
        if dias_atraso < 121:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operación Denegada: El crédito no cumple el umbral mínimo de 121 días de mora (días actuales: {dias_atraso})."
            )
        if cargo not in ("JEFE_REGIONAL", "RIESGOS", "COMITE"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operación Denegada: La transición a cobranza judicial está reservada al Jefe Regional o superior (su rol: {cargo})."
            )
    elif nuevo_estado_upper == 'CASTIGO':
        if dias_atraso < 181:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operación Denegada: El crédito no cumple el umbral mínimo de 180 días de mora para castigo (días actuales: {dias_atraso})."
            )
        if cargo not in ("RIESGOS", "COMITE"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operación Denegada: El castigo de créditos incobrables requiere aprobación del Comité de Riesgos (su rol: {cargo})."
            )
    else:
        raise HTTPException(status_code=400, detail="Estado de destino de transición no válido.")

    # 3. Transicionar
    try:
        res = repo_recuperaciones.transicionar_estado_credito(conn, pkcuentacredito, nuevo_estado_upper)
        
        # Registrar esta transición en el historial de cobranza
        repo_recuperaciones.registrar_gestion_cobranza(
            conn,
            pkcuentacredito=pkcuentacredito,
            codtipogestion="JUDI" if nuevo_estado_upper == 'JUDICIAL' else "SMS", # fallback, representativo
            resultado=f"TRANSICIÓN A {nuevo_estado_upper} exitosa por {cargo}.",
            compromisopago=None,
            montocomprometido=None,
            gestor=cargo
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
