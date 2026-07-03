"""Controlador de registro y onboarding paso a paso."""
from fastapi import HTTPException, status
import re

# Mock base de datos de invitaciones (en memoria para el simulador)
# Formato: { "codigo": {"dni": "12345678", "celular": "999888777", "estado": "paso_2"} }
INVITACIONES_MOCK = {
    "GNB-2026-XQW1": {
        "dni": "11111111", 
        "celular": "987654321", 
        "estado": "paso_2",
        "pin_sms": "123456"
    }
}

def validar_codigo_invitacion(codigo: str) -> dict:
    if codigo not in INVITACIONES_MOCK:
        raise HTTPException(status_code=400, detail="Código de invitación inválido o caducado.")
    
    data = INVITACIONES_MOCK[codigo]
    return {
        "mensaje": "Código validado correctamente",
        "dni": data["dni"],
        "siguiente_paso": "otp"
    }

def generar_y_enviar_otp(codigo: str) -> dict:
    if codigo not in INVITACIONES_MOCK:
        raise HTTPException(status_code=400, detail="Código no encontrado.")
    
    # Simula el envío de SMS
    celular = INVITACIONES_MOCK[codigo]["celular"]
    pin_generado = "123456" # Hardcodeado para simulación
    INVITACIONES_MOCK[codigo]["pin_sms"] = pin_generado
    
    return {
        "mensaje": f"Se ha enviado un código SMS al número terminado en ...{celular[-3:]}",
        "siguiente_paso": "validar_otp"
    }

def validar_otp(codigo: str, pin: str) -> dict:
    if codigo not in INVITACIONES_MOCK:
        raise HTTPException(status_code=400, detail="Código no encontrado.")
    
    if pin != INVITACIONES_MOCK[codigo].get("pin_sms"):
        raise HTTPException(status_code=400, detail="PIN SMS incorrecto.")
    
    return {
        "mensaje": "Identidad validada.",
        "siguiente_paso": "biometria"
    }

def simular_biometria(codigo: str, foto_hash: str) -> dict:
    # Simula que la foto (selfie) coincide con el DNI en Reniec
    if codigo not in INVITACIONES_MOCK:
        raise HTTPException(status_code=400, detail="Código no encontrado.")
    if not foto_hash:
        raise HTTPException(status_code=400, detail="Debe proporcionar una imagen para biometría.")
    
    return {
        "mensaje": "Biometría facial exitosa. Rasgos coinciden 98%.",
        "siguiente_paso": "credenciales"
    }

def registrar_credenciales(codigo: str, username: str, password: str, sello_seguridad: str) -> dict:
    if codigo not in INVITACIONES_MOCK:
        raise HTTPException(status_code=400, detail="Código no encontrado.")
    
    if len(username) < 5:
        raise HTTPException(status_code=400, detail="El nombre de usuario debe tener mínimo 5 caracteres.")
    
    # Validar contraseña segura
    if len(password) < 8 or not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password) or not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Contraseña debe tener 8 caracteres, mayúsculas, minúsculas y números.")
        
    if not sello_seguridad:
        raise HTTPException(status_code=400, detail="Debe seleccionar un Sello de Seguridad.")

    # Aquí deberíamos insertar/actualizar en la base de datos real (USUARIOS_HOMEBANKING)
    # Por ahora en el simulador avanzamos el flujo
    
    return {
        "mensaje": "Credenciales y Sello de Seguridad creados exitosamente.",
        "siguiente_paso": "token"
    }

def activar_token_digital(codigo: str, codigo_activacion_email: str) -> dict:
    if codigo not in INVITACIONES_MOCK:
        raise HTTPException(status_code=400, detail="Código no encontrado.")
    
    if codigo_activacion_email != "GNBTK-123": # Mock de código enviado por email
        raise HTTPException(status_code=400, detail="Código de activación de Token inválido.")
        
    # El usuario está listo para operar
    return {
        "mensaje": "Token Digital sincronizado exitosamente. Registro completado.",
        "estado": "COMPLETO"
    }
