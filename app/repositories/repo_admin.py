"""Repositorio de consultas administrativas globales del banco.

Schema real del core financiero Andino:
  - dcliente: codcliente, nomcliente, email, numerodocumentoidentidad,
              numerotelefonopersonal, fecultactualizacion
  - dcuentaahorro + fcuentaahorro  → snapshot por cuenta (MAX periododia)
  - dcuentacredito + fagcuentacredito → cartera mensual PERIODO_CARTERA=202512
  - foperaciones → kardex unificado
"""
from sqlalchemy.engine import Connection
from sqlalchemy import text

PERIODO_CARTERA = 202512   # periodo mensual activo en fagcuentacredito


def stats_globales(conn: Connection) -> dict:
    """Consolida métricas globales del banco."""

    # ── Ahorros (snapshot más reciente de cada cuenta) ───────────────────────
    r_aho = conn.execute(text("""
        SELECT
            COALESCE(SUM(CASE WHEN TRIM(m.codmoneda) = 'PEN'
                              THEN f.montosaldocapitaltotal ELSE 0 END), 0) AS total_pen,
            COALESCE(SUM(CASE WHEN TRIM(m.codmoneda) = 'USD'
                              THEN f.montosaldocapitaltotal ELSE 0 END), 0) AS total_usd,
            COUNT(DISTINCT a.pkcuentaahorro)                                 AS cnt
        FROM dcuentaahorro a
        JOIN fcuentaahorro f ON f.pkcuentaahorro = a.pkcuentaahorro
            AND f.periododia = (
                SELECT MAX(f2.periododia) FROM fcuentaahorro f2
                WHERE f2.pkcuentaahorro = a.pkcuentaahorro)
        JOIN dmoneda m ON m.pkmoneda = f.pkmoneda
    """)).fetchone()
    total_ahorro_pen   = float(r_aho[0]) if r_aho else 0
    total_ahorro_usd   = float(r_aho[1]) if r_aho else 0
    cnt_cuentas_ahorro = int(r_aho[2])   if r_aho else 0

    # ── Distribución por tipo de cuenta ahorro ────────────────────────────────
    rows_dist = conn.execute(text("""
        SELECT
            tca.destipocuentaahorro                         AS tipo,
            COALESCE(SUM(f.montosaldocapitaltotal), 0)      AS total
        FROM dcuentaahorro a
        JOIN fcuentaahorro f ON f.pkcuentaahorro = a.pkcuentaahorro
            AND f.periododia = (
                SELECT MAX(f2.periododia) FROM fcuentaahorro f2
                WHERE f2.pkcuentaahorro = a.pkcuentaahorro)
        JOIN dtipocuentaahorro tca ON tca.pktipocuentaahorro = f.pktipocuentaahorro
        GROUP BY tca.destipocuentaahorro
        ORDER BY total DESC
    """)).fetchall()
    dist_productos = [{"tipo": r[0], "total": float(r[1])} for r in rows_dist]

    # ── Créditos (periodo de cartera activo) ─────────────────────────────────
    r_cre = conn.execute(text("""
        SELECT
            COALESCE(SUM(fa.montoaprobadocredito), 0)   AS monto_otorgado,
            COALESCE(SUM(fa.montosaldocliente), 0)      AS deuda_total,
            COUNT(DISTINCT fa.pkcuentacredito)          AS cnt_creditos
        FROM fagcuentacredito fa
        WHERE fa.periodomes = :periodo
    """), {"periodo": PERIODO_CARTERA}).fetchone()
    monto_total_otorgado = float(r_cre[0]) if r_cre else 0
    deuda_total          = float(r_cre[1]) if r_cre else 0
    cnt_creditos         = int(r_cre[2])   if r_cre else 0

    # ── Clasificación SBS ─────────────────────────────────────────────────────
    rows_sbs = conn.execute(text("""
        SELECT
            COALESCE(cal.descalificacioncrediticia, 'Normal') AS clasificacion,
            COUNT(*)                                           AS cantidad,
            COALESCE(SUM(fa.montosaldocliente), 0)            AS monto
        FROM fagcuentacredito fa
        LEFT JOIN dcalificacioncrediticia cal
            ON cal.pkcalificacioncrediticia = fa.pkcalificacioncrediticiainterna
        WHERE fa.periodomes = :periodo
        GROUP BY cal.descalificacioncrediticia
        ORDER BY monto DESC
    """), {"periodo": PERIODO_CARTERA}).fetchall()
    cartera_sbs = [
        {"clasificacion": r[0], "cantidad": int(r[1]), "monto": float(r[2])}
        for r in rows_sbs
    ]

    # ── Grupos de mora ────────────────────────────────────────────────────────
    rows_mora = conn.execute(text("""
        SELECT
            CASE
                WHEN diasatrasocredito = 0               THEN 'Al día'
                WHEN diasatrasocredito BETWEEN 1 AND 30  THEN '1–30 días'
                WHEN diasatrasocredito BETWEEN 31 AND 60 THEN '31–60 días'
                WHEN diasatrasocredito BETWEEN 61 AND 90 THEN '61–90 días'
                ELSE '+90 días'
            END AS grupo,
            COUNT(*)                               AS cantidad,
            COALESCE(SUM(montosaldocliente), 0)   AS monto
        FROM fagcuentacredito
        WHERE periodomes = :periodo
        GROUP BY grupo
        ORDER BY MIN(
            CASE
                WHEN diasatrasocredito = 0               THEN 0
                WHEN diasatrasocredito BETWEEN 1 AND 30  THEN 1
                WHEN diasatrasocredito BETWEEN 31 AND 60 THEN 2
                WHEN diasatrasocredito BETWEEN 61 AND 90 THEN 3
                ELSE 4
            END)
    """), {"periodo": PERIODO_CARTERA}).fetchall()
    mora = [{"grupo": r[0], "cantidad": int(r[1]), "monto": float(r[2])} for r in rows_mora]

    # ── Total clientes ────────────────────────────────────────────────────────
    r_cli = conn.execute(text("SELECT COUNT(*) FROM dcliente")).fetchone()
    cnt_clientes = int(r_cli[0]) if r_cli else 0

    return {
        "clientes_activos": cnt_clientes,
        "cuentas_ahorro_activas": cnt_cuentas_ahorro,
        "creditos_activos": cnt_creditos,
        "total_ahorro_pen": total_ahorro_pen,
        "total_ahorro_usd": total_ahorro_usd,
        "monto_total_otorgado": monto_total_otorgado,
        "deuda_total": deuda_total,
        "dist_productos_ahorro": dist_productos,
        "cartera_sbs": cartera_sbs,
        "mora": mora,
    }


def listar_clientes(conn: Connection) -> list:
    """Retorna clientes con conteo de cuentas y créditos."""
    rows = conn.execute(text("""
        SELECT
            c.pkcliente                                          AS pkcliente,
            TRIM(c.codcliente)                                   AS codcliente,
            TRIM(c.nomcliente)                                   AS nombre,
            c.email                                              AS email,
            c.numerodocumentoidentidad                           AS nro_documento,
            COUNT(DISTINCT ca.pkcuentaahorro)                    AS cnt_ahorros,
            COUNT(DISTINCT cc.pkcuentacredito)                   AS cnt_creditos
        FROM dcliente c
        LEFT JOIN dcuentaahorro ca ON ca.pkcliente = c.pkcliente
        LEFT JOIN dcuentacredito cc ON cc.pkcliente = c.pkcliente
        GROUP BY c.pkcliente, c.codcliente, c.nomcliente,
                 c.email, c.numerodocumentoidentidad
        ORDER BY c.nomcliente
        LIMIT 500
    """)).fetchall()
    return [
        {
            "pkcliente": r[0],
            "codcliente": r[1],
            "nombre": r[2],
            "email": r[3],
            "nro_documento": r[4],
            "cnt_ahorros": int(r[5]),
            "cnt_creditos": int(r[6]),
            # sin campo "estado" en dcliente real
            "estado": "A",
        }
        for r in rows
    ]


# ─── Exports para Power BI ────────────────────────────────────────────────────

def powerbi_clientes(conn: Connection) -> list:
    rows = conn.execute(text("""
        SELECT
            TRIM(c.codcliente)              AS codcliente,
            TRIM(c.nomcliente)              AS nombre,
            c.codtipodocumentoidentidad     AS tipo_documento,
            c.numerodocumentoidentidad      AS nro_documento,
            c.email                         AS email,
            c.numerotelefonopersonal        AS telefono,
            c.fechaingresocaja::date        AS fecha_registro
        FROM dcliente c
        ORDER BY c.codcliente
        LIMIT 2000
    """)).fetchall()
    cols = ["codcliente","nombre","tipo_documento","nro_documento",
            "email","telefono","fecha_registro"]
    return [dict(zip(cols, r)) for r in rows]


def powerbi_ahorros(conn: Connection) -> list:
    rows = conn.execute(text("""
        SELECT
            TRIM(a.codcuentaahorro)         AS codcuentaahorro,
            TRIM(c.codcliente)              AS codcliente,
            TRIM(c.nomcliente)              AS cliente,
            tca.destipocuentaahorro         AS tipo,
            m.desmoneda                     AS moneda,
            f.montosaldocapitaltotal        AS saldo,
            f.tasaefectivaanual             AS tasa,
            ec.desestadocuenta              AS estado,
            f.fechaaperturacuenta           AS fecha_apertura
        FROM dcuentaahorro a
        JOIN dcliente c ON c.pkcliente = a.pkcliente
        JOIN fcuentaahorro f ON f.pkcuentaahorro = a.pkcuentaahorro
            AND f.periododia = (
                SELECT MAX(f2.periododia) FROM fcuentaahorro f2
                WHERE f2.pkcuentaahorro = a.pkcuentaahorro)
        JOIN dtipocuentaahorro tca ON tca.pktipocuentaahorro = f.pktipocuentaahorro
        JOIN destadocuenta ec      ON ec.pkestadocuenta      = f.pkestadocuenta
        JOIN dmoneda m             ON m.pkmoneda             = f.pkmoneda
        ORDER BY a.codcuentaahorro
        LIMIT 2000
    """)).fetchall()
    cols = ["codcuentaahorro","codcliente","cliente","tipo","moneda","saldo",
            "tasa","estado","fecha_apertura"]
    return [dict(zip(cols, r)) for r in rows]


def powerbi_creditos(conn: Connection) -> list:
    rows = conn.execute(text("""
        SELECT
            TRIM(cr.codcuentacredito)                          AS codcuentacredito,
            TRIM(c.codcliente)                                 AS codcliente,
            TRIM(c.nomcliente)                                 AS cliente,
            fa.montoaprobadocredito                            AS monto_otorgado,
            fa.montosaldocapital                               AS saldo_capital,
            fa.montosaldocliente                               AS pago_pendiente,
            fa.tasainterescompensatoria                        AS tasa_tea,
            fa.nrocuotas                                       AS plazo_meses,
            fa.diasatrasocredito                               AS dias_atraso,
            COALESCE(cal.descalificacioncrediticia, 'Normal')  AS calificacion_sbs,
            fa.fechadesembolsocredito                          AS fecha_desembolso
        FROM dcuentacredito cr
        JOIN dcliente c ON c.pkcliente = cr.pkcliente
        JOIN fagcuentacredito fa ON fa.pkcuentacredito = cr.pkcuentacredito
            AND fa.periodomes = :periodo
        LEFT JOIN dcalificacioncrediticia cal
            ON cal.pkcalificacioncrediticia = fa.pkcalificacioncrediticiainterna
        ORDER BY cr.codcuentacredito
        LIMIT 2000
    """), {"periodo": PERIODO_CARTERA}).fetchall()
    cols = ["codcuentacredito","codcliente","cliente","monto_otorgado","saldo_capital",
            "pago_pendiente","tasa_tea","plazo_meses","dias_atraso","calificacion_sbs",
            "fecha_desembolso"]
    return [dict(zip(cols, r)) for r in rows]


def powerbi_operaciones(conn: Connection) -> list:
    rows = conn.execute(text("""
        SELECT
            o.pkoperacion                                       AS codoperacion,
            top2.destipooperacion                               AS tipo_operacion,
            o.montooperacion                                    AS monto,
            m.desmoneda                                         AS moneda,
            o.fechahoraoperacion::date                          AS fecha_operacion,
            co.desconceptooperacion                             AS descripcion,
            TRIM(COALESCE(ca.codcuentaahorro, cc.codcuentacredito,'')) AS codigo_cuenta,
            TRIM(COALESCE(c.nomcliente,''))                     AS cliente
        FROM foperaciones o
        JOIN dconceptooperacion co   ON co.pkconceptooperacion = o.pkconceptooperacion
        JOIN dtipooperacion top2     ON top2.pktipooperacion    = o.pktipooperacion
        JOIN dmoneda m               ON m.pkmoneda              = o.pkmoneda
        LEFT JOIN dcuentaahorro ca   ON ca.pkcuentaahorro       = o.pkcuentaahorro
        LEFT JOIN dcuentacredito cc  ON cc.pkcuentacredito      = o.pkcuentacredito
        LEFT JOIN dcliente c         ON c.pkcliente = COALESCE(ca.pkcliente, cc.pkcliente)
        ORDER BY o.fechahoraoperacion DESC, o.pkoperacion DESC
        LIMIT 5000
    """)).fetchall()
    cols = ["codoperacion","tipo_operacion","monto","moneda","fecha_operacion",
            "descripcion","codigo_cuenta","cliente"]
    return [dict(zip(cols, r)) for r in rows]
