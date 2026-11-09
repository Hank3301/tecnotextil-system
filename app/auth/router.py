"""Rota de autenticação: login e refresh token."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import LoginRequest, LoginResponse, RefreshRequest, Token, UsuarioResumo
from app.auth.security import criar_tokens, decodificar_token, verificar_senha
from app.database import get_db
from app.models.models import Usuario

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login de usuário",
    description="Autentica usuário e retorna access token + refresh token",
)
def login(dados: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    usuario = db.query(Usuario).filter(Usuario.ds_login == dados.login.lower()).first()

    if not usuario or not verificar_senha(dados.senha, usuario.ds_senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token = criar_tokens(usuario.id_usuario, usuario.ds_cargo)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        usuario=UsuarioResumo.model_validate(usuario),
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Renovar access token",
    description="Usa refresh token para gerar novo par de tokens",
)
def refresh(dados: RefreshRequest) -> Token:
    payload = decodificar_token(dados.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        )

    usuario_id = int(payload.get("sub", 0))
    cargo = payload.get("cargo")

    if not usuario_id or not cargo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado",
        )

    access_token, new_refresh_token = criar_tokens(usuario_id, cargo)

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )