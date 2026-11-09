"""Schemas de autenticação e autorização."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    usuario_id: Optional[int] = None
    cargo: Optional[str] = None


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    senha: str = Field(..., min_length=8, max_length=128)


class LoginResponse(Token):
    usuario: "UsuarioResumo"


class UsuarioResumo(BaseModel):
    id_usuario: int
    nm_usuario: str
    ds_cargo: str
    ds_login: str

    model_config = ConfigDict(from_attributes=True)


class RefreshRequest(BaseModel):
    refresh_token: str