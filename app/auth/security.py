"""Segurança: Hash de senhas (bcrypt) e JWT tokens."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import SecretStr

from app.config import get_settings

settings = get_settings()


# Configuração do bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    """Gera hash bcrypt da senha."""
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Verifica se a senha confere com o hash armazenado."""
    return pwd_context.verify(senha, hash_armazenado)


# Configuração JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


def criar_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um access token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def criar_refresh_token(data: dict) -> str:
    """Cria um refresh token JWT de longa duração."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Decodifica e valida um token JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def criar_tokens(usuario_id: int, cargo: str) -> tuple[str, str]:
    """Cria par access+refresh token para um usuário."""
    data = {"sub": str(usuario_id), "cargo": cargo}
    access_token = criar_access_token(data)
    refresh_token = criar_refresh_token(data)
    return access_token, refresh_token