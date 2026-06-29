from fastapi import APIRouter
from app.controllers import ctrl_registro
from app.schemas.sch_registro import (
    CodigoInvitacionRequest,
    OTPRequest,
    BiometriaRequest,
    CredencialesRequest,
    TokenRequest
)

router = APIRouter(prefix="/registro", tags=["registro"])

@router.post("/validar-codigo")
def validar_codigo(body: CodigoInvitacionRequest):
    return ctrl_registro.validar_codigo_invitacion(body.codigo)

@router.post("/enviar-otp")
def enviar_otp(body: CodigoInvitacionRequest):
    return ctrl_registro.generar_y_enviar_otp(body.codigo)

@router.post("/validar-otp")
def validar_otp(body: OTPRequest):
    return ctrl_registro.validar_otp(body.codigo, body.pin)

@router.post("/biometria")
def biometria(body: BiometriaRequest):
    return ctrl_registro.simular_biometria(body.codigo, body.foto_hash)

@router.post("/credenciales")
def credenciales(body: CredencialesRequest):
    return ctrl_registro.registrar_credenciales(body.codigo, body.username, body.password, body.sello_seguridad)

@router.post("/token")
def token(body: TokenRequest):
    return ctrl_registro.activar_token_digital(body.codigo, body.codigo_activacion_email)
