from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_gerente
from app.database import get_db
from app.schemas.schemas import UsuarioCreate, UsuarioResponse, UsuarioUpdate
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/api/v1/usuarios", tags=["Cadastro de Usuários"], dependencies=[Depends(require_gerente)])


@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED, summary="Cadastra um usuário")
def criar_usuario(dados: UsuarioCreate, db: Session = Depends(get_db)):
    return UsuarioService.criar(db, dados)


@router.get("", response_model=List[UsuarioResponse], summary="Lista usuários")
def listar_usuarios(
    ds_cargo: Optional[str] = Query(None, description="Filtro exato por cargo (ex.: CORTADOR)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return UsuarioService.listar(db, ds_cargo=ds_cargo, skip=skip, limit=limit)


@router.get("/{id_usuario}", response_model=UsuarioResponse, summary="Consulta um usuário")
def obter_usuario(id_usuario: int, db: Session = Depends(get_db)):
    return UsuarioService.obter(db, id_usuario)


@router.patch("/{id_usuario}", response_model=UsuarioResponse, summary="Atualiza parcialmente um usuário")
def atualizar_usuario(id_usuario: int, dados: UsuarioUpdate, db: Session = Depends(get_db)):
    return UsuarioService.atualizar(db, id_usuario, dados)


@router.delete(
    "/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui um usuário sem histórico (409 se houver ordens de corte)",
)
def excluir_usuario(id_usuario: int, db: Session = Depends(get_db)):
    UsuarioService.excluir(db, id_usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
