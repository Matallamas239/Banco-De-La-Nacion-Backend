"""Repository of collection and recoveries (MPR - Mora/Recuperaciones)."""
from decimal import Decimal
from datetime import date
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.repositories.repo_cuentas import PERIODO_CARTERA

def get_recuperaciones_stats(conn: Connection) -> dict:
    """Calcula estadísticas generales de la cartera en mora (periodo de cartera activo)."""
    # 1. KPIs Generales
    kpis = conn.execute(
        text("""
            SELECT
                COALESCE(SUM(montosaldocliente), 0) AS total_mora,
                COUNT(DISTINCT pkcuentacredito) AS cant_creditos
            FROM fagcuentacredito
            WHERE periodomes = :periodo AND diasatrasocredito > 0
        """),
        {"periodo": PERIODO_CARTERA}
    ).fetchone()
    
    total_mora = float(kpis[0]) if kpis else 0.0
    cant_creditos = int(kpis[1]) if kpis else 0

    # 2. Distribución por bandas
    dist = conn.execute(
        text("""
            SELECT
                CASE
                    WHEN diasatrasocredito = 0 THEN 'PREVENTIVA'
                    WHEN diasatrasocredito BETWEEN 1 AND 30 THEN 'TEMPRANA'
                    WHEN diasatrasocredito BETWEEN 31 AND 120 THEN 'TARDIA'
                    WHEN diasatrasocredito BETWEEN 121 AND 180 THEN 'JUDICIAL'
                    ELSE 'CASTIGO'
                END AS banda,
                COUNT(*) AS cantidad,
                COALESCE(SUM(montosaldocliente), 0) AS monto
            FROM fagcuentacredito
            WHERE periodomes = :periodo
            GROUP BY banda
        """),
        {"periodo": PERIODO_CARTERA}
    ).fetchall()

    bandas_map = {r[0]: {"cantidad": int(r[1]), "monto": float(r[2])} for r in dist}
    
    # Asegurar que todas las bandas estén presentes
    for b in ['PREVENTIVA', 'TEMPRANA', 'TARDIA', 'JUDICIAL', 'CASTIGO']:
        if b not in bandas_map:
            bandas_map[b] = {"cantidad": 0, "monto": 0.0}

    return {
        "total_mora": total_mora,
        "cant_creditos_mora": cant_creditos,
        "distribucion_bandas": bandas_map
    }

def listar_cartera_mora(conn: Connection, banda: str) -> list[dict]:
    """Retorna los créditos en mora correspondientes a una banda de atraso."""
    if banda == 'PREVENTIVA':
        condicion = "fa.diasatrasocredito = 0"
    elif banda == 'TEMPRANA':
        condicion = "fa.diasatrasocredito BETWEEN 1 AND 30"
    elif banda == 'TARDIA':
        condicion = "fa.diasatrasocredito BETWEEN 31 AND 120"
    elif banda == 'JUDICIAL':
        condicion = "fa.diasatrasocredito BETWEEN 121 AND 180"
    elif banda == 'CASTIGO':
        condicion = "fa.diasatrasocredito > 180"
    else:
        condicion = "fa.diasatrasocredito >= 0"

    sql = text(f"""
        SELECT 
            cr.pkcuentacredito,
            TRIM(cr.codcuentacredito) AS codcuentacredito,
            TRIM(c.codcliente) AS codcliente,
            TRIM(c.nomcliente) AS cliente,
            c.numerodocumentoidentidad AS nro_documento,
            fa.diasatrasocredito AS dias_atraso,
            fa.montosaldocapital AS saldo_capital,
            fa.montosaldocliente AS pago_pendiente,
            TRIM(ec.desestadocredito) AS estado_credito,
            fa.pkestadocredito
        FROM dcuentacredito cr
        JOIN dcliente c ON c.pkcliente = cr.pkcliente
        JOIN fagcuentacredito fa ON fa.pkcuentacredito = cr.pkcuentacredito AND fa.periodomes = :periodo
        JOIN destadocredito ec ON ec.pkestadocredito = fa.pkestadocredito
        WHERE {condicion}
        ORDER BY fa.diasatrasocredito DESC, cr.codcuentacredito
    """)

    rows = conn.execute(sql, {"periodo": PERIODO_CARTERA}).mappings().all()
    return [dict(r) for r in rows]

def registrar_gestion_cobranza(
    conn: Connection,
    pkcuentacredito: int,
    codtipogestion: str,
    resultado: str,
    compromisopago: str | None,
    montocomprometido: Decimal | None,
    gestor: str
) -> dict:
    """Registra una nueva gestión de cobranza en fgestioncobranza."""
    # 1. Obtener días de atraso actuales y banda
    credito = conn.execute(
        text("""
            SELECT diasatrasocredito 
            FROM fagcuentacredito 
            WHERE pkcuentacredito = :pk AND periodomes = :periodo
        """),
        {"pk": pkcuentacredito, "periodo": PERIODO_CARTERA}
    ).mappings().first()
    
    if not credito:
        raise ValueError("Crédito no encontrado en la cartera actual.")

    dias_atraso = credito["diasatrasocredito"]
    
    # Determinar banda
    if dias_atraso == 0:
        banda = 'PREVENTIVA'
    elif dias_atraso <= 30:
        banda = 'TEMPRANA'
    elif dias_atraso <= 120:
        banda = 'TARDIA'
    elif dias_atraso <= 180:
        banda = 'JUDICIAL'
    else:
        banda = 'CASTIGO'

    # 2. Resolver pktipogestion
    pktipogestion = conn.execute(
        text("SELECT pktipogestion FROM dtipogestioncobranza WHERE codtipogestion = :cod"),
        {"cod": codtipogestion}
    ).scalar()
    
    if not pktipogestion:
        # Fallback al primer tipo existente
        pktipogestion = conn.execute(text("SELECT MIN(pktipogestion) FROM dtipogestioncobranza")).scalar()

    # 3. Insertar registro
    comp_date = date.fromisoformat(compromisopago) if compromisopago else None
    
    conn.execute(
        text("""
            INSERT INTO fgestioncobranza (
                pkcuentacredito, pktipogestion, fechagestion, diasatrasoalmomento,
                banda, gestor, resultado, compromisopago, montocomprometido, fecultactualizacion
            ) VALUES (
                :pk, :tip, CURRENT_DATE, :dias,
                :banda, :gestor, :res, :comp, :monto, NOW()
            )
        """),
        {
            "pk": pkcuentacredito,
            "tip": pktipogestion,
            "dias": dias_atraso,
            "banda": banda,
            "gestor": gestor,
            "res": resultado,
            "comp": comp_date,
            "monto": montocomprometido
        }
    )
    conn.commit()
    return {"mensaje": "Gestión de cobranza registrada correctamente."}

def listar_historial_cobranza(conn: Connection, pkcuentacredito: int) -> list[dict]:
    """Retorna el historial de cobranzas realizadas a una cuenta de crédito."""
    sql = text("""
        SELECT 
            g.fechagestion AS fecha,
            TRIM(t.destipogestion) AS tipo_gestion,
            g.diasatrasoalmomento AS dias_atraso,
            TRIM(g.banda) AS banda,
            TRIM(g.gestor) AS gestor,
            TRIM(g.resultado) AS resultado,
            g.compromisopago AS compromiso_fecha,
            g.montocomprometido AS compromiso_monto
        FROM fgestioncobranza g
        JOIN dtipogestioncobranza t ON t.pktipogestion = g.pktipogestion
        WHERE g.pkcuentacredito = :pk
        ORDER BY g.fechagestion DESC, g.pkgestion DESC
    """)
    rows = conn.execute(sql, {"pk": pkcuentacredito}).mappings().all()
    return [dict(r) for r in rows]

def transicionar_estado_credito(conn: Connection, pkcuentacredito: int, nuevo_estado: str) -> dict:
    """Actualiza el estado administrativo del crédito a Cobranza Judicial o Castigado."""
    # Resolver PK de destadocredito
    if nuevo_estado == 'JUDICIAL':
        cod_estado = '03'  # En Cobranza Judicial
    elif nuevo_estado == 'CASTIGO':
        cod_estado = '07'  # Castigado
    else:
        raise ValueError("Estado de transición no soportado.")

    pkestado = conn.execute(
        text("SELECT pkestadocredito FROM destadocredito WHERE codestadocredito = :cod"),
        {"cod": cod_estado}
    ).scalar()

    if not pkestado:
        raise ValueError(f"Estado de destino '{nuevo_estado}' no configurado en la BD.")

    # Actualizar estado en la cartera activa
    conn.execute(
        text("""
            UPDATE fagcuentacredito 
            SET pkestadocredito = :pkest, fecultactualizacion = NOW()
            WHERE pkcuentacredito = :pk AND periodomes = :periodo
        """),
        {"pkest": pkestado, "pk": pkcuentacredito, "periodo": PERIODO_CARTERA}
    )
    conn.commit()
    return {"mensaje": f"Crédito transicionado exitosamente a estado: {nuevo_estado}."}
