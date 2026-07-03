"""Router de administrador: estadísticas globales del banco y endpoints para Power BI.

Todos los endpoints exigen un token JWT con tipo == 'admin'.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.controllers import ctrl_admin, ctrl_recuperaciones
from app.core.cfg_database import get_db
from app.core.cfg_security import decodificar_token
from app.schemas.sch_creditos import SolicitudCreditoRequest
from app.schemas.sch_admin import ClienteCrearRequest, GestionCobranzaRequest, TransicionMoraRequest
from app.repositories import repo_creditos

bearer_scheme = HTTPBearer(auto_error=True)


def get_admin(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """Valida que el token JWT tenga tipo == 'admin' and adds the active cargo."""
    payload = decodificar_token(creds.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("tipo") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a administradores",
        )
    # Read active role from header (useful to switch roles in the Admin interface)
    cargo = request.headers.get("x-admin-role", "ASESOR").upper()
    payload["cargo"] = cargo
    return payload


router = APIRouter(
    prefix="/admin",
    tags=["administración"],
    dependencies=[Depends(get_admin)],
)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/stats", summary="Estadísticas globales del banco")
def stats(conn: Connection = Depends(get_db)):
    """Consolida KPIs, distribución de productos, cartera SBS y mora."""
    return ctrl_admin.stats_globales(conn)

@router.get("/clientes", summary="Listado de todos los clientes")
def clientes(conn: Connection = Depends(get_db)):
    """Retorna todos los clientes con conteo de cuentas y créditos."""
    return ctrl_admin.listar_clientes(conn)


@router.get("/clientes/buscar", summary="Buscar clientes por query (nombre, documento o código)")
def buscar_clientes(q: str, conn: Connection = Depends(get_db)):
    """Busca clientes por coincidencia."""
    return ctrl_admin.buscar_clientes(conn, q)


@router.post("/clientes/crear", summary="Registrar nuevo cliente en ventanilla")
def crear_cliente(req: ClienteCrearRequest, conn: Connection = Depends(get_db)):
    """Registra un nuevo cliente con cuenta de ahorro y acceso a Homebanking."""
    try:
        return ctrl_admin.crear_cliente(conn, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/solicitudes", summary="Listar todas las solicitudes")
def get_solicitudes(conn: Connection = Depends(get_db)):
    """Lista todas las solicitudes."""
    return repo_creditos.listar_solicitudes(conn)


@router.post("/creditos/solicitar", summary="Registrar solicitud a nombre de un cliente")
def solicitar_credito(req: SolicitudCreditoRequest, conn: Connection = Depends(get_db)):
    """Registra una solicitud de crédito actuando como el cliente especificado."""
    if not req.pkcliente:
        raise HTTPException(status_code=400, detail="pkcliente es requerido para admin")
    try:
        res = repo_creditos.crear_solicitud(
            conn,
            pkcliente=req.pkcliente,
            montosolicitud=req.montosolicitud,
            plazo=req.plazo,
            codtipocredito=req.codtipocredito,
            codactividadeconomica=req.codactividadeconomica,
            montoingresoneto=req.montoingresoneto,
            con_seguro=req.con_seguro,
            fecha_desembolso=req.fecha_desembolso,
            dia_pago=req.dia_pago
        )
    except ValueError as e:
        if "Semáforo ROJO" in str(e):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return res


@router.post("/solicitudes/{id}/evaluar", summary="Evaluar solicitud y generar cronograma")
def evaluar_solicitud(id: int, conn: Connection = Depends(get_db), admin: dict = Depends(get_admin)):
    """Pasa la solicitud a 'Aprobado' y retorna el cronograma temporal.

    Aplica reglas de negocio por niveles de aprobación (cargo).
    """
    sol = conn.execute(
        text("SELECT montosolicitudcredito FROM dsolicitud WHERE pksolicitud = :id"),
        {"id": id}
    ).mappings().first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    monto = sol["montosolicitudcredito"]
    cargo = admin.get("cargo", "ASESOR")

    if monto > 25000 and cargo in ("ASESOR", "JEFE_REGIONAL"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Aprobación Denegada: Créditos mayores a S/ 25,000 requieren resolución del Comité de Riesgos (su rol actual: {cargo})."
        )
    if monto > 10000 and cargo == "ASESOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Aprobación Denegada: Créditos mayores a S/ 10,000 requieren aprobación del Jefe Regional (su rol actual: {cargo})."
        )

    try:
        return repo_creditos.evaluar_solicitud(conn, id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/solicitudes/{id}/desembolsar", summary="Desembolsar solicitud aprobada")
def desembolsar_solicitud(id: int, conn: Connection = Depends(get_db), admin: dict = Depends(get_admin)):
    """Crea la cuenta de crédito, el cronograma oficial y abona el saldo a la cuenta de ahorros."""
    cargo = admin.get("cargo", "ASESOR")
    if cargo == "COMITE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación Denegada: El Comité de Riesgos no realiza desembolsos operativos."
        )
    try:
        return repo_creditos.desembolsar_solicitud(conn, id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Endpoints Power BI (formato plano JSON) ──────────────────────────────────

@router.get("/powerbi/clientes", summary="[Power BI] Clientes")
def pb_clientes(conn: Connection = Depends(get_db)):
    return ctrl_admin.powerbi_clientes(conn)


@router.get("/powerbi/ahorros", summary="[Power BI] Cuentas de Ahorro")
def pb_ahorros(conn: Connection = Depends(get_db)):
    return ctrl_admin.powerbi_ahorros(conn)


@router.get("/powerbi/creditos", summary="[Power BI] Cartera de Créditos")
def pb_creditos(conn: Connection = Depends(get_db)):
    return ctrl_admin.powerbi_creditos(conn)


@router.get("/powerbi/operaciones", summary="[Power BI] Transacciones")
def pb_operaciones(conn: Connection = Depends(get_db)):
    return ctrl_admin.powerbi_operaciones(conn)


# ─── Recuperaciones / Mora ───────────────────────────────────────────────────

@router.get("/recuperaciones/stats", summary="Métricas de cobranzas y mora")
def get_rec_stats(conn: Connection = Depends(get_db)):
    return ctrl_recuperaciones.stats(conn)


@router.get("/recuperaciones/cartera", summary="Cartera morosa por banda de mora")
def get_rec_cartera(banda: str, conn: Connection = Depends(get_db)):
    return ctrl_recuperaciones.listar_cartera(conn, banda)


@router.post("/recuperaciones/gestiones", summary="Registrar gestión de cobranza")
def registrar_gestion(req: GestionCobranzaRequest, conn: Connection = Depends(get_db), admin: dict = Depends(get_admin)):
    gestor = admin.get("cargo", "ASESOR")
    return ctrl_recuperaciones.registrar_gestion(
        conn,
        pkcuentacredito=req.pkcuentacredito,
        codtipogestion=req.codtipogestion,
        resultado=req.resultado,
        compromisopago=req.compromisopago,
        montocomprometido=req.montocomprometido,
        gestor=gestor
    )


@router.get("/recuperaciones/gestiones/{pkcuentacredito}", summary="Historial de cobranzas de un crédito")
def get_historial(pkcuentacredito: int, conn: Connection = Depends(get_db)):
    return ctrl_recuperaciones.historial(conn, pkcuentacredito)


@router.post("/recuperaciones/transicionar", summary="Transicionar crédito a Judicial o Castigo")
def transicionar_estado(req: TransicionMoraRequest, conn: Connection = Depends(get_db), admin: dict = Depends(get_admin)):
    cargo = admin.get("cargo", "ASESOR")
    return ctrl_recuperaciones.transicionar(conn, req.pkcuentacredito, req.nuevo_estado, cargo)
