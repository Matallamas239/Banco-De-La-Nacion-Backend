"""Controlador de administración: orquesta llamadas al repositorio."""
from sqlalchemy.engine import Connection
from app.repositories import repo_admin


def stats_globales(conn: Connection) -> dict:
    return repo_admin.stats_globales(conn)


def listar_clientes(conn: Connection) -> list:
    return repo_admin.listar_clientes(conn)


def powerbi_clientes(conn: Connection) -> list:
    return repo_admin.powerbi_clientes(conn)


def powerbi_ahorros(conn: Connection) -> list:
    return repo_admin.powerbi_ahorros(conn)


def powerbi_creditos(conn: Connection) -> list:
    return repo_admin.powerbi_creditos(conn)


def powerbi_operaciones(conn: Connection) -> list:
    return repo_admin.powerbi_operaciones(conn)
