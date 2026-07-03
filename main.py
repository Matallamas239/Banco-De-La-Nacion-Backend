"""HOMEBANKING — Backend FastAPI · Banca Internet Banco GNB.

Portal del CLIENTE. Proyecto separado del core bancario; se conecta a la base
PostgreSQL YA EXISTENTE BancoGNB (no crea tablas). Corre en el puerto 8002.

Levantar:  uvicorn main:app --reload --port 8002
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cfg_config import settings
from app.routes import route_auth, route_creditos, route_cuentas, route_operaciones, route_admin, route_info

app = FastAPI(
    title="Banca Internet Banco GNB — Homebanking API",
    description="Portal del cliente de Banca Internet Banco GNB. Solo consultas y "
    "operaciones del cliente del portal (dcliente / usuarios_homebanking).",
    version="1.0.0",
)

@app.on_event("startup")
def startup_db_setup():
    from app.core.cfg_database import engine
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fpedir_info (
                pkpedirinfo         SERIAL PRIMARY KEY,
                nombre              VARCHAR(100) NOT NULL,
                email               VARCHAR(100) NOT NULL,
                telefono            VARCHAR(20) NOT NULL,
                producto            VARCHAR(50) NOT NULL,
                mensaje             TEXT,
                fecha_registro      TIMESTAMP DEFAULT NOW()
            );
        """))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://images.unsplash.com;"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

app.include_router(route_auth.router)
app.include_router(route_cuentas.router)
app.include_router(route_operaciones.router)
app.include_router(route_creditos.router)
app.include_router(route_admin.router)
app.include_router(route_info.router)


@app.get("/", tags=["root"])
def raiz():
    return {
        "servicio": "Banca Internet Banco GNB — Homebanking API",
        "version": "1.0.0",
        "estado": "ok",
        "docs": "/docs",
        "puerto": settings.PORT,
    }
