"""Escrituras SQL para solicitar un crédito (registro en dsolicitud).

Alcance: solo Microempresa (ME) y Consumo (CO).
"""
from decimal import Decimal
import math
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.repositories.repo_cuentas import PERIODO_CARTERA

# codtipocredito del portal -> codtipocredito en dproducto
MAPA_TIPO_CREDITO = {"ME": "01", "CO": "03"}  # ME=Microempresa, CO=Consumo
ESTADO_EN_EVALUACION = "01"  # dsolicitudestado.codsolicitudestado

def listar_solicitudes(conn: Connection) -> list[dict]:
    """Lista todas las solicitudes de crédito."""
    sql = text(
        """
        SELECT s.pksolicitud as id, s.codsolicitud, s.pkcliente, c.nomcliente, c.numerodocumentoidentidad,
               s.montosolicitudcredito as monto, s.plazosolicitudcredito as plazo, s.fechasolicitudcredito as fecha,
               e.dessolicitudestado as estado, s.pksolicitudestado
        FROM dsolicitud s
        JOIN dcliente c ON c.pkcliente = s.pkcliente
        JOIN dsolicitudestado e ON e.pksolicitudestado = s.pksolicitudestado
        ORDER BY s.pksolicitud DESC
        """
    )
    return [dict(r) for r in conn.execute(sql).mappings().all()]


def _pk_producto_por_tipo(conn: Connection, cod_tipo_producto: str) -> int | None:
    return conn.execute(
        text(
            """
            SELECT MIN(pkproducto) FROM dproducto
            WHERE TRIM(codtipocredito) = :cod AND flagactivo = '1'
            """
        ),
        {"cod": cod_tipo_producto},
    ).scalar()


def _pk_estado_solicitud(conn: Connection, cod: str) -> int | None:
    return conn.execute(
        text("SELECT pksolicitudestado FROM dsolicitudestado WHERE TRIM(codsolicitudestado) = :c"),
        {"c": cod},
    ).scalar()


def _pk_actividad(conn: Connection, cod: str) -> int | None:
    return conn.execute(
        text("SELECT pkactividadeconomica FROM dactividadeconomica WHERE TRIM(codactividadeconomica) = :c"),
        {"c": cod},
    ).scalar()


def _agencia_asesor_del_cliente(conn: Connection, pkcliente: int) -> tuple[int, int]:
    """Toma agencia/asesor del crédito vigente del cliente; si no tiene, usa valores por defecto."""
    row = conn.execute(
        text(
            """
            SELECT pkagencia, pkasesor FROM fagcuentacredito
            WHERE pkcliente = :pk AND periodomes = :periodo
            ORDER BY pkcuentacredito DESC LIMIT 1
            """
        ),
        {"pk": pkcliente, "periodo": PERIODO_CARTERA},
    ).first()
    if row:
        return row[0], row[1]
    # Fallback: primera agencia activa y primer asesor existentes
    pkag = conn.execute(text("SELECT MIN(pkagencia) FROM dagencia")).scalar()
    pkas = conn.execute(text("SELECT MIN(pkasesor) FROM dasesor")).scalar()
    return pkag, pkas


def upsert_fuente_ingreso(
    conn: Connection, pkcliente: int, montoingresoneto: Decimal, pkactividad: int | None
) -> None:
    """Registra el ingreso del cliente (PK compuesta pkcliente+periodomes) de forma idempotente."""
    conn.execute(
        text(
            """
            INSERT INTO fclientefuenteingreso (pkcliente, periodomes, montofuenteingreso,
                                               pkactividadeconomicacliente, fecultactualizacion)
            VALUES (:pk, :periodo, :monto, :act, now())
            ON CONFLICT (pkcliente, periodomes)
            DO UPDATE SET montofuenteingreso = EXCLUDED.montofuenteingreso,
                          pkactividadeconomicacliente = EXCLUDED.pkactividadeconomicacliente,
                          fecultactualizacion = now()
            """
        ),
        {"pk": pkcliente, "periodo": PERIODO_CARTERA, "monto": montoingresoneto, "act": pkactividad},
    )


def crear_solicitud(
    conn: Connection,
    pkcliente: int,
    montosolicitud: Decimal,
    plazo: int,
    codtipocredito: str,
    codactividadeconomica: str,
    montoingresoneto: Decimal,
    con_seguro: bool = True,
    fecha_desembolso: str | None = None,
    dia_pago: int | None = None,
) -> dict:
    """Registra una solicitud en dsolicitud (estado inicial 'En Evaluación' o 'En Comité' según monto).

    pksolicitud proviene de dsolicitud_pksolicitud_seq y codsolicitud se deriva
    con 'SOL' || LPAD(currval(...)::text, 7, '0').
    """
    tea = Decimal('0.4092') if con_seguro else Decimal('0.4392')
    cod_tipo_producto = MAPA_TIPO_CREDITO[codtipocredito]
    pkproducto = _pk_producto_por_tipo(conn, cod_tipo_producto)
    if pkproducto is None:
        raise ValueError(f"No hay producto activo para el tipo de crédito '{codtipocredito}'")

    pkactividad = _pk_actividad(conn, codactividadeconomica)
    if pkactividad is None:
        raise ValueError(f"Actividad económica '{codactividadeconomica}' no encontrada")

    pkmoneda = conn.execute(
        text("SELECT pkmoneda FROM dmoneda WHERE TRIM(codmoneda) = 'SO'")
    ).scalar()
    pkagencia, pkasesor = _agencia_asesor_del_cliente(conn, pkcliente)

    # ─── EVALUACIÓN DE ELEGIBILIDAD / SCORING Y SEMÁFORO ───
    # 1. Calcular Cuota Nueva del Crédito
    tem = Decimal(math.pow(1 + float(tea), 1/12.0) - 1)
    if tem == 0:
        new_cuota = montosolicitud / plazo
    else:
        new_cuota = montosolicitud * (tem * Decimal(math.pow(1 + float(tem), plazo))) / (Decimal(math.pow(1 + float(tem), plazo)) - 1)
    new_cuota = round(new_cuota, 2)

    # 2. Obtener cuotas mensuales activas de créditos vigentes
    active_quotas = conn.execute(
        text("""
            SELECT COALESCE(SUM(f1.montocuota), 0)
            FROM fplanpagomes f1
            WHERE f1.pkcliente = :pkcliente
              AND f1.fechapagocuota IS NULL
              AND f1.nrocuota = (
                  SELECT MIN(f2.nrocuota)
                  FROM fplanpagomes f2
                  WHERE f2.pkcuentacredito = f1.pkcuentacredito
                    AND f2.fechapagocuota IS NULL
              )
        """),
        {"pkcliente": pkcliente}
    ).scalar() or Decimal('0.00')

    # 3. Calcular RDS (Ratio Deuda-Ingreso)
    total_obligaciones = Decimal(active_quotas) + new_cuota
    if montoingresoneto > 0:
        rds = (total_obligaciones / montoingresoneto) * 100
    else:
        rds = Decimal('999.99')

    # 4. Obtener calificación SBS interna más reciente (peor de sus créditos activos)
    sbs_val = conn.execute(
        text("""
            SELECT COALESCE(MAX(CAST(cal.codcalificacioncrediticia AS INTEGER)), 0)
            FROM fagcuentacredito fa
            JOIN dcalificacioncrediticia cal ON cal.pkcalificacioncrediticia = fa.pkcalificacioncrediticiainterna
            WHERE fa.pkcliente = :pkcliente AND fa.periodomes = :periodo
        """),
        {"pkcliente": pkcliente, "periodo": PERIODO_CARTERA}
    ).scalar() or 0

    sbs_labels = {0: "Normal", 1: "Con Problemas Potenciales (CPP)", 2: "Deficiente", 3: "Dudoso", 4: "Pérdida"}
    sbs_label = sbs_labels.get(sbs_val, "Normal")

    # 5. Regla Normativa del Semáforo
    if rds > 40 or sbs_val >= 2:
        raise ValueError(
            f"Evaluación de Elegibilidad Fallida: Semáforo ROJO. "
            f"El Ratio Deuda-Ingreso es de {rds:.1f}% (límite permitido: 40.0%) y su calificación SBS es {sbs_label}."
        )

    # 6. Determinar nivel de aprobación y estado inicial por monto
    if montosolicitud > 25000:
        estado_solicitada = "06"  # En Comité
        cod_nivel = "N4"          # Comité de Créditos Agencia (Nivel de Comité)
    elif montosolicitud > 10000:
        estado_solicitada = "01"  # En Evaluación
        cod_nivel = "N2"          # Administrador de Agencia (Jefe Regional)
    else:
        estado_solicitada = "01"  # En Evaluación
        cod_nivel = "N1"          # Asesor de Negocios

    pkestado = conn.execute(
        text("SELECT pksolicitudestado FROM dsolicitudestado WHERE codsolicitudestado = :cod"),
        {"cod": estado_solicitada}
    ).scalar()

    pknivel = conn.execute(
        text("SELECT pknivelaprobacion FROM dnivelaprobacion WHERE codnivelaprobacion = :cod"),
        {"cod": cod_nivel}
    ).scalar()

    # Registra/actualiza la fuente de ingreso (idempotente) antes de la solicitud.
    upsert_fuente_ingreso(conn, pkcliente, montoingresoneto, pkactividad)

    row = conn.execute(
        text(
            """
            INSERT INTO dsolicitud (
                pksolicitud, codsolicitud, pkcliente, codlineacredito,
                pksolicitudestado, pknivelaprobacion, pkmoneda, pkproducto,
                codtiposolicitud, destiposolicitud,
                montosolicitudcredito, nrocuotasolicitud, plazosolicitudcredito,
                fechasolicitudcredito, codususol,
                flaglibreamortizacioncredito, nrodiasgracia,
                pkactividadeconomicasolicitud, pkagencia, pkasesor,
                tasainterescompensatoria, diafechafija, fechaaprobacioncredito,
                fechahoracreacion, fechahoraultmodificacion, fecultactualizacion
            ) VALUES (
                nextval('dsolicitud_pksolicitud_seq'),
                'SOL' || LPAD(currval('dsolicitud_pksolicitud_seq')::text, 7, '0'),
                :pkcliente, 'CR',
                :pkestado, :pknivel, :pkmoneda, :pkproducto,
                '01', 'Credito Nuevo',
                :monto, :plazo, :plazo,
                CURRENT_DATE, 'HB',
                'N', 0,
                :pkactividad, :pkagencia, :pkasesor,
                :tea, :dia_pago, :fecha_desembolso,
                now(), now(), now()
            )
            RETURNING pksolicitud, codsolicitud
            """
        ),
        {
            "pkcliente": pkcliente,
            "pkestado": pkestado,
            "pknivel": pknivel,
            "pkmoneda": pkmoneda,
            "pkproducto": pkproducto,
            "monto": montosolicitud,
            "plazo": plazo,
            "pkactividad": pkactividad,
            "pkagencia": pkagencia,
            "pkasesor": pkasesor,
            "tea": tea,
            "dia_pago": dia_pago,
            "fecha_desembolso": datetime.strptime(fecha_desembolso, "%Y-%m-%d").date() if fecha_desembolso else None,
        },
    ).mappings().first()
    conn.commit()
    return {"pksolicitud": row["pksolicitud"], "codsolicitud": row["codsolicitud"].strip()}

def evaluar_solicitud(conn: Connection, pksolicitud: int) -> dict:
    """Genera cronograma preliminar y aprueba solicitud."""
    # Obtenemos datos de la solicitud
    sol = conn.execute(
        text("SELECT * FROM dsolicitud WHERE pksolicitud = :pk"),
        {"pk": pksolicitud}
    ).mappings().first()
    if not sol:
        raise ValueError("Solicitud no encontrada")

    pkestado_aprobado = _pk_estado_solicitud(conn, "02") # 02 = Aprobado (asumiendo) o actualizamos a mano
    if not pkestado_aprobado:
        # Fallback al string '02' si no hay funcion
        pkestado_aprobado = conn.execute(text("SELECT pksolicitudestado FROM dsolicitudestado WHERE codsolicitudestado='02'")).scalar()
    
    conn.execute(
        text("UPDATE dsolicitud SET pksolicitudestado = :est WHERE pksolicitud = :pk"),
        {"est": pkestado_aprobado, "pk": pksolicitud}
    )

    tea = sol["tasainterescompensatoria"] or Decimal('0.4392')
    monto = sol["montosolicitudcredito"]
    plazo = sol["plazosolicitudcredito"]
    dia_pago = sol["diafechafija"] or 1
    fecha_desembolso = sol["fechaaprobacioncredito"] or date.today()

    # Cálculo TEM y Cuota Fija Francesa
    tem = Decimal(math.pow(1 + float(tea), 1/12.0) - 1)
    if tem == 0:
        cuota = monto / plazo
    else:
        cuota = monto * (tem * Decimal(math.pow(1 + float(tem), plazo))) / (Decimal(math.pow(1 + float(tem), plazo)) - 1)
    cuota = round(cuota, 2)

    cronograma = []
    saldo = monto
    fecha_pago = fecha_desembolso
    # Ir al primer mes
    for _ in range(plazo):
        # Avanzar 1 mes
        fecha_pago = fecha_pago + relativedelta(months=1)
        # Ajustar día de pago
        try:
            fecha_pago = fecha_pago.replace(day=dia_pago)
        except ValueError:
            # Si el día es 31 y el mes tiene 30, ir al último día del mes
            fecha_pago = fecha_pago + relativedelta(day=31)

        interes = round(saldo * tem, 2)
        capital = cuota - interes
        if saldo - capital < 0:
            capital = saldo
            cuota = capital + interes
            saldo = Decimal(0)
        else:
            saldo -= capital

        cronograma.append({
            "nrocuota": len(cronograma) + 1,
            "fecha_vencimiento": fecha_pago.strftime("%Y-%m-%d"),
            "monto_cuota": cuota,
            "capital": capital,
            "interes": interes,
            "saldo_capital": saldo
        })
    conn.commit()
    return {"cronograma": cronograma, "monto_total": sum(c["monto_cuota"] for c in cronograma)}

def desembolsar_solicitud(conn: Connection, pksolicitud: int) -> dict:
    """Crea la cuenta de crédito, el cronograma en fplanpagomes y abona al ahorro."""
    sol = conn.execute(
        text("SELECT * FROM dsolicitud WHERE pksolicitud = :pk"),
        {"pk": pksolicitud}
    ).mappings().first()
    if not sol:
        raise ValueError("Solicitud no encontrada")

    pkestado_desembolsado = conn.execute(text("SELECT pksolicitudestado FROM dsolicitudestado WHERE codsolicitudestado='04'")).scalar()
    conn.execute(text("UPDATE dsolicitud SET pksolicitudestado = :est WHERE pksolicitud = :pk"), {"est": pkestado_desembolsado, "pk": pksolicitud})

    # Crear cuenta credito
    row_credito = conn.execute(
        text("INSERT INTO dcuentacredito (codcuentacredito, codlineacredito, pkcliente) VALUES ('CRE' || :pk, 'CR', :cli) RETURNING pkcuentacredito"),
        {"pk": pksolicitud, "cli": sol["pkcliente"]}
    ).first()
    pkcuentacredito = row_credito[0]

    eval_result = evaluar_solicitud(conn, pksolicitud)
    cronograma = eval_result["cronograma"]

    # Fplanpagomes
    pkmoneda = sol["pkmoneda"]
    pkproducto = sol["pkproducto"]
    pkcliente = sol["pkcliente"]
    pkagencia = sol["pkagencia"]
    pkasesor = sol["pkasesor"]

    # fagcuentacredito
    fecha_desembolso = sol["fechaaprobacioncredito"] or date.today()
    tea = sol["tasainterescompensatoria"] or Decimal('0.4392')

    conn.execute(
        text('''
        INSERT INTO fagcuentacredito (
            periodomes, pkcuentacredito, pksolicitud, pkestadocredito, nrocuotas,
            montoaprobadocredito, montocapitaldesembolsado, pkproducto, pkmoneda,
            tasainterescompensatoria, tasainteresmoratoria, fechadesembolsocredito,
            pkcliente, pkagencia, pkasesor, montosaldocapital, montosaldocliente
        ) VALUES (
            :periodo, :pkcc, :pksol, 1, :plazo,
            :monto, :monto, :pkprod, :pkmon,
            :tea, 0.0, :fechades,
            :cli, :age, :ase, :monto, :monto
        )
        '''),
        {
            "periodo": PERIODO_CARTERA, "pkcc": pkcuentacredito, "pksol": pksolicitud, "plazo": sol["plazosolicitudcredito"],
            "monto": sol["montosolicitudcredito"], "pkprod": pkproducto, "pkmon": pkmoneda,
            "tea": tea, "fechades": fecha_desembolso, "cli": pkcliente, "age": pkagencia, "ase": pkasesor
        }
    )

    for c in cronograma:
        conn.execute(
            text('''
            INSERT INTO fplanpagomes (
                periodomes, pkcuentacredito, codplanpago, nrocuota, pksolicitud,
                pkestadocredito, pkproducto, pkmoneda, pkcliente, pkagencia, pkasesor,
                fechavencimientopagocuota, montocuota, montosaldo,
                montointeresprogramado, montocapitalprogramado, montosaldocapital
            ) VALUES (
                :periodo, :pkcc, :cod, :nro, :pksol,
                1, :pkprod, :pkmon, :cli, :age, :ase,
                :fechaven, :cuota, :cuota,
                :interes, :capital, :saldocap
            )
            '''),
            {
                "periodo": PERIODO_CARTERA, "pkcc": pkcuentacredito, "cod": f"P{pksolicitud}-{c['nrocuota']}",
                "nro": c['nrocuota'], "pksol": pksolicitud, "pkprod": pkproducto, "pkmon": pkmoneda,
                "cli": pkcliente, "age": pkagencia, "ase": pkasesor,
                "fechaven": c["fecha_vencimiento"], "cuota": c["monto_cuota"],
                "interes": c["interes"], "capital": c["capital"], "saldocap": c["saldo_capital"]
            }
        )

    # Abono a cuenta de ahorros
    cuenta_ahorro = conn.execute(
        text("SELECT pkcuentaahorro FROM dcuentaahorro WHERE pkcliente = :cli LIMIT 1"),
        {"cli": pkcliente}
    ).scalar()
    
    if cuenta_ahorro:
        conn.execute(
            text("UPDATE fcuentaahorro SET montosaldocapitaltotal = montosaldocapitaltotal + :monto WHERE pkcuentaahorro = :pkah"),
            {"monto": sol["montosolicitudcredito"], "pkah": cuenta_ahorro}
        )
        conn.execute(
            text('''
            INSERT INTO foperaciones (
                codtipkar, pkcuentacredito, pkcuentaahorro, codkardex, pkconceptooperacion,
                fechahoraoperacion, periododia, pktipooperacion, pkmoneda,
                pkagenciaorigen, codtipoegresoingreso, montooperacion
            ) VALUES (
                'DE', :pkcc, :pkah, 'DESEMBOLSO', 1,
                now(), 20260202, 1, :pkmon,
                :age, 'I', :monto
            )
            '''),
            {
                "pkcc": pkcuentacredito, "pkah": cuenta_ahorro, "pkmon": pkmoneda, "age": pkagencia,
                "monto": sol["montosolicitudcredito"]
            }
        )

    conn.commit()
    return {"mensaje": "Crédito desembolsado exitosamente", "pkcuentacredito": pkcuentacredito}
