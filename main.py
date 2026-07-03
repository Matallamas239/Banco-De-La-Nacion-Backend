"""HOMEBANKING — Backend FastAPI · Banca Internet Banco GNB.

Portal del CLIENTE. Proyecto separado del core bancario; se conecta a la base
PostgreSQL YA EXISTENTE BancoDeLaNacion (no crea tablas). Corre en el puerto 8002.

Levantar:  uvicorn main:app --reload --port 8002
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cfg_config import settings
from app.routes import route_auth, route_creditos, route_cuentas, route_operaciones, route_admin, route_registro, route_tarjetas

app = FastAPI(
    title="Banca Internet Banco GNB — Homebanking API",
    description="Portal del cliente de Banca Internet Banco GNB. Solo consultas y "
    "operaciones del cliente del portal (dcliente / usuarios_homebanking).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(route_auth.router)
app.include_router(route_cuentas.router)
app.include_router(route_operaciones.router)
app.include_router(route_creditos.router)
app.include_router(route_admin.router)
app.include_router(route_registro.router)
app.include_router(route_tarjetas.router)

@app.get("/", tags=["root"])
def raiz():
    return {
        "servicio": "Banca Internet Banco GNB — Homebanking API",
        "version": "1.0.0",
        "estado": "ok",
        "docs": "/docs",
        "puerto": settings.PORT,
    }
