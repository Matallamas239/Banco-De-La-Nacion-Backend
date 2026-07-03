from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection
from sqlalchemy import text
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_cliente
from app.routes.route_admin import get_admin

router = APIRouter(tags=["información"])

class PedirInfoRequest(BaseModel):
    nombre: str
    email: str
    telefono: str
    producto: str
    mensaje: Optional[str] = None

@router.post("/public/pedir-info", summary="Solicitud de información pública")
def pedir_info_publico(req: PedirInfoRequest, conn: Connection = Depends(get_db)):
    sql = text("""
        INSERT INTO fpedir_info (nombre, email, telefono, producto, mensaje)
        VALUES (:nom, :em, :tel, :prod, :msg)
        RETURNING pkpedirinfo
    """)
    pk = conn.execute(sql, {
        "nom": req.nombre,
        "em": req.email,
        "tel": req.telefono,
        "prod": req.producto,
        "msg": req.mensaje
    }).scalar()
    conn.commit()
    return {"mensaje": "Solicitud de información registrada con éxito", "id": pk}

@router.post("/operaciones/pedir-info", summary="Solicitud de información de cliente logueado")
def pedir_info_cliente(req: PedirInfoRequest, conn: Connection = Depends(get_db), cliente: dict = Depends(get_cliente)):
    sql = text("""
        INSERT INTO fpedir_info (nombre, email, telefono, producto, mensaje)
        VALUES (:nom, :em, :tel, :prod, :msg)
        RETURNING pkpedirinfo
    """)
    pk = conn.execute(sql, {
        "nom": req.nombre,
        "em": req.email,
        "tel": req.telefono,
        "prod": req.producto,
        "msg": req.mensaje
    }).scalar()
    conn.commit()
    return {"mensaje": "Solicitud de información de cliente registrada con éxito", "id": pk}

@router.get("/admin/pedir-info", summary="Listar solicitudes de información recibidas")
def listar_pedir_info(conn: Connection = Depends(get_db), admin: dict = Depends(get_admin)):
    sql = text("""
        SELECT pkpedirinfo AS id, nombre, email, telefono, producto, mensaje, fecha_registro
        FROM fpedir_info
        ORDER BY fecha_registro DESC
    """)
    rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]
