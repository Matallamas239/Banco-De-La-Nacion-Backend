"""Controlador de Tarjetas de Crédito."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.engine import Connection
from sqlalchemy import text

def consolidacion_deuda(
    conn: Connection,
    pkcliente: int,
    banco_origen: str,
    tipo_tarjeta: str,
    cci_pago: str,
    monto_consolidar: Decimal,
    plazo_meses: int
) -> dict:
    """
    Simula la compra de deuda. Transfiere saldos de otros bancos a la tarjeta GNB.
    Costo de verificación: S/ 3.50.
    """
    if len(cci_pago) != 20 or not cci_pago.isdigit():
        raise HTTPException(status_code=400, detail="El CCI debe contener exactamente 20 dígitos numéricos.")
        
    if plazo_meses < 12 or plazo_meses > 36:
        raise HTTPException(status_code=400, detail="El plazo de amortización debe estar entre 12 y 36 meses.")
        
    if monto_consolidar <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="El monto a consolidar debe ser mayor a 0.")

    comision_verificacion = Decimal("3.50")
    
    # En una implementación real, aquí se verifica el límite de la tarjeta del cliente
    # y se inserta el nuevo plan de pagos (FPLANPAGOMES).
    
    return {
        "mensaje": "Solicitud de compra de deuda procesada exitosamente.",
        "banco_origen": banco_origen,
        "monto_consolidado": monto_consolidar,
        "plazo_meses": plazo_meses,
        "comision_verificacion": comision_verificacion,
        "total_cargado_a_linea": monto_consolidar + comision_verificacion,
        "estado": "APROBADO"
    }

def disposicion_efectivo(
    conn: Connection,
    pkcliente: int,
    codcuentacredito: str,
    monto_retiro: Decimal,
    linea_credito_total: Decimal
) -> dict:
    """
    Simula la disposición de efectivo de una tarjeta de crédito.
    Tope máximo: 35% de la línea total.
    """
    tope_maximo = linea_credito_total * Decimal("0.35")
    
    if monto_retiro > tope_maximo:
        raise HTTPException(
            status_code=400, 
            detail=f"El monto excede el tope máximo para disposición de efectivo (S/ {tope_maximo:,.2f})"
        )
        
    # Validar si la configuración permite disposición de efectivo
    query = text("""
        SELECT disposicion_efectivo FROM fconfiguracion_tarjeta f
        JOIN dcuentacredito c ON c.pkcuentacredito = f.pkcuentacredito
        WHERE c.codcuentacredito = :cod AND c.pkcliente = :pkcliente
    """)
    row = conn.execute(query, {"cod": codcuentacredito, "pkcliente": pkcliente}).mappings().first()
    
    if row and row["disposicion_efectivo"] == "N":
        raise HTTPException(status_code=403, detail="La disposición de efectivo está deshabilitada en la configuración de seguridad.")

    # En una implementación real, aquí se registra el cargo a la línea.
    
    return {
        "mensaje": "Disposición de efectivo aprobada.",
        "monto_retirado": monto_retiro,
        "estado": "APROBADO"
    }

def actualizar_configuracion_seguridad(
    conn: Connection,
    pkcliente: int,
    codcuentacredito: str,
    compras_internet: str = None,
    compras_exterior: str = None,
    disposicion_efectivo: str = None,
    sobregiro: str = None
) -> dict:
    """
    Actualiza los flags de seguridad de la tarjeta.
    """
    # Primero obtener el pkcuentacredito
    query_cta = text("SELECT pkcuentacredito FROM dcuentacredito WHERE codcuentacredito = :cod AND pkcliente = :pkcliente")
    row_cta = conn.execute(query_cta, {"cod": codcuentacredito, "pkcliente": pkcliente}).mappings().first()
    
    if not row_cta:
        raise HTTPException(status_code=404, detail="Tarjeta de crédito no encontrada.")
        
    pkcuentacredito = row_cta["pkcuentacredito"]
    
    # Crear o actualizar
    query = text("""
        INSERT INTO fconfiguracion_tarjeta 
        (pkcuentacredito, compras_internet, compras_exterior, disposicion_efectivo, sobregiro)
        VALUES (:pk, COALESCE(:int, 'S'), COALESCE(:ext, 'N'), COALESCE(:efe, 'S'), COALESCE(:sob, 'N'))
        ON CONFLICT (pkcuentacredito) DO UPDATE SET
            compras_internet = COALESCE(:int, fconfiguracion_tarjeta.compras_internet),
            compras_exterior = COALESCE(:ext, fconfiguracion_tarjeta.compras_exterior),
            disposicion_efectivo = COALESCE(:efe, fconfiguracion_tarjeta.disposicion_efectivo),
            sobregiro = COALESCE(:sob, fconfiguracion_tarjeta.sobregiro),
            fecultactualizacion = now()
    """)
    
    conn.execute(query, {
        "pk": pkcuentacredito,
        "int": compras_internet,
        "ext": compras_exterior,
        "efe": disposicion_efectivo,
        "sob": sobregiro
    })
    conn.commit()
    
    return {
        "mensaje": "Configuración de seguridad actualizada exitosamente."
    }
