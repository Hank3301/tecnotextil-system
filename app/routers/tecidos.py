from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_gerente
from app.database import get_db
from app.schemas.schemas import TecidoCreate, TecidoResponse, TecidoUpdate
from app.services.tecido_service import TecidoService

router = APIRouter(prefix="/api/v1/tecidos", tags=["Cadastro de Tecidos"], dependencies=[Depends(require_gerente)])


@router.post("", response_model=TecidoResponse, status_code=status.HTTP_201_CREATED, summary="Cadastra um tecido")
def criar_tecido(dados: TecidoCreate, db: Session = Depends(get_db)):
    return TecidoService.criar(db, dados)


@router.get("", response_model=List[TecidoResponse], summary="Lista tecidos")
def listar_tecidos(
    busca: Optional[str] = Query(None, description="Filtra por código ou nome"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return TecidoService.listar(db, busca=busca, skip=skip, limit=limit)


@router.get("/{id_tecido}", response_model=TecidoResponse, summary="Consulta um tecido")
def obter_tecido(id_tecido: int, db: Session = Depends(get_db)):
    return TecidoService.obter(db, id_tecido)


@router.patch("/{id_tecido}", response_model=TecidoResponse, summary="Atualiza parcialmente um tecido")
def atualizar_tecido(id_tecido: int, dados: TecidoUpdate, db: Session = Depends(get_db)):
    return TecidoService.atualizar(db, id_tecido, dados)


@router.delete(
    "/{id_tecido}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui um tecido sem lotes (409 se houver lotes)",
)
def excluir_tecido(id_tecido: int, db: Session = Depends(get_db)):
    TecidoService.excluir(db, id_tecido)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
