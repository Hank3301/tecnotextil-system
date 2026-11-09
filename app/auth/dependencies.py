"""Dependências FastAPI para autenticação e RBAC."""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decodificar_token
from app.database import get_db
from app.models.models import Usuario


# Esquema de autenticação Bearer
security = HTTPBearer(auto_error=False)


class UsuarioAutenticado:
    """Usuário atual autenticado com dados do token."""
    def __init__(self, usuario_id: int, cargo: str):
        self.usuario_id = usuario_id
        self.cargo = cargo


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> UsuarioAutenticado:
    """
    Dependência que valida o token JWT e retorna o usuário autenticado.
    Levanta 401 se token inválido, expirado ou usuário não encontrado.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decodificar_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tipo de token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario_id = int(payload.get("sub", 0))
    cargo = payload.get("cargo")

    if not usuario_id or not cargo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verifica se usuário ainda existe no banco
    usuario = db.query(Usuario).filter(Usuario.id_usuario == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UsuarioAutenticado(usuario_id=usuario_id, cargo=cargo)


def require_role(*cargos_permitidos: str):
    """
    Factory de dependência que exige um dos cargos permitidos.
    Uso: `Depends(require_role("GERENTE", "VENDEDOR"))`
    """
    def _check_role(user: UsuarioAutenticado = Depends(get_current_user)) -> UsuarioAutenticado:
        if user.cargo not in cargos_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Cargos permitidos: {', '.join(cargos_permitidos)}",
            )
        return user
    return _check_role


# Atalhos para os 3 perfis
require_gerente = require_role("GERENTE")
require_vendedor = require_role("VENDEDOR", "GERENTE")
require_cortador = require_role("CORTADOR", "GERENTE")
require_operador = require_role("VENDEDOR", "CORTADOR", "GERENTE")