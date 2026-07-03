"""Pruebas Automatizadas de Ciberseguridad.

Este script utiliza TestClient de FastAPI para simular y auditar vulnerabilidades y controles
de seguridad en el Homebanking del Banco GNB.

Ejecutar con:  python test_security.py
"""
import sys
import os
from fastapi.testclient import TestClient

# Añadir directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app

client = TestClient(app)

def run_security_tests():
    print("======================================================================")
    print("INICIANDO PRUEBAS DE CIBERSEGURIDAD - PORTAL FINANCIERO GNB")
    print("======================================================================\n")

    errors = 0

    # 1. Verificar Cabeceras de Seguridad HTTP (OWASP / Helmet Equivalente)
    print("1. Validando cabeceras de ciberseguridad...")
    r_root = client.get("/")
    
    headers_to_check = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    for header, expected_val in headers_to_check.items():
        val = r_root.headers.get(header)
        if val == expected_val:
            print(f"  [OK] {header} = '{val}'")
        else:
            print(f"  [ERROR] {header} es '{val}' pero se esperaba '{expected_val}'")
            errors += 1

    csp = r_root.headers.get("Content-Security-Policy")
    if csp and "default-src 'self'" in csp:
        print(f"  [OK] Content-Security-Policy = '{csp[:60]}...'")
    else:
        print(f"  [ERROR] Content-Security-Policy ausente o incorrecta")
        errors += 1
    print()

    # 2. Verificar Aislamiento de Autenticación y Autorización
    print("2. Validando aislamiento de endpoints privados sin token...")
    endpoints_to_test = [
        "/cuentas/ahorro",
        "/cuentas/credito",
        "/operaciones/servicios",
        "/admin/stats"
    ]

    for ep in endpoints_to_test:
        r = client.get(ep)
        if r.status_code == 403 or r.status_code == 401:
            print(f"  [OK] Acceso denegado de forma segura a {ep} (HTTP {r.status_code})")
        else:
            print(f"  [ERROR] Endpoint {ep} expuesto sin credenciales (HTTP {r.status_code})")
            errors += 1
    print()

    # 3. Validar Prevención de Inyección SQL (SQL Injection - SQLi)
    # Enviando payloads maliciosos comunes en el login
    print("3. Validando prevención de Inyección SQL (SQLi)...")
    sqli_payloads = [
        {"username": "' OR '1'='1", "password": "xyz"},
        {"username": "admin' --", "password": "xyz"},
        {"username": "cli000007; DROP TABLE dcliente CASCADE; --", "password": "xyz"}
    ]

    for payload in sqli_payloads:
        r = client.post("/auth/login", json=payload)
        # El backend debe rechazar o devolver 401/error controlado (datos inválidos), sin romper la base de datos o fallar con 500
        if r.status_code == 401 or r.status_code == 400:
            print(f"  [OK] Intento de inyección SQL mitigado con éxito para '{payload['username']}' (HTTP {r.status_code})")
        elif r.status_code == 500:
            print(f"  [ERROR] Posible brecha o error de servidor (HTTP 500) ante inyección: '{payload['username']}'")
            errors += 1
        else:
            print(f"  [ALERTA] HTTP {r.status_code} devuelto para inyección SQL")
    print()

    print("======================================================================")
    if errors == 0:
        print("RESULTADO: TODAS LAS PRUEBAS DE CIBERSEGURIDAD PASARON CON ÉXITO [OK]")
        print("======================================================================")
        return True
    else:
        print(f"RESULTADO: SE ENCONTRARON {errors} FALLOS DE SEGURIDAD")
        print("======================================================================")
        return False

if __name__ == "__main__":
    success = run_security_tests()
    sys.exit(0 if success else 1)
