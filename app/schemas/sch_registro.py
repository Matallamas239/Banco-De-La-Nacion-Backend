from pydantic import BaseModel, Field

class CodigoInvitacionRequest(BaseModel):
    codigo: str

class OTPRequest(BaseModel):
    codigo: str
    pin: str

class BiometriaRequest(BaseModel):
    codigo: str
    foto_hash: str = Field(..., description="Imagen en base64 o hash")

class CredencialesRequest(BaseModel):
    codigo: str
    username: str
    password: str
    sello_seguridad: str

class TokenRequest(BaseModel):
    codigo: str
    codigo_activacion_email: str
