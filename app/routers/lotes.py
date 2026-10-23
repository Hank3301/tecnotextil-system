from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import (
    LoteTingimentoCreate, LoteTingimentoResponse, LoteTingimentoResumo, LoteTingimentoUpdate,
)
from app.services.lote_service import LoteService

router = APIRouter(prefix="/api/v1/lotes", tags=["Cadastro de Lotes de Tingimento"])


@router.post(
    "", response_model=LoteTingimentoResumo, status_code=status.HTTP_201_CREATED,
    summary="Cadastra um lote de tingimento (partida) para um tecido",
)
def criar_lote(dados: LoteTingimentoCreate, db: Session = Depends(get_db)):
    return LoteService.criar(db, dados)


@router.get("", response_model=List[LoteTingimentoResumo], summary="Lista lotes (sem os rolos)")
def listar_lotes(
    id_tecido: Optional[int] = Query(None),
    cd_partida: Optional[str] = Query(None),
    ds_tonalidade_cor: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return LoteService.listar(
        db, id_tecido=id_tecido, cd_partida=cd_partida, ds_tonalidade_cor=ds_tonalidade_cor,
        skip=skip, limit=limit,
    )


@router.get("/{id_lote}", response_model=LoteTingimentoResponse, summary="Consulta um lote com seus rolos")
def obter_lote(id_lote: int, db: Session = Depends(get_db)):
    return LoteService.obter(db, id_lote)


@router.patch("/{id_lote}", response_model=LoteTingimentoResumo, summary="Atualiza parcialmente um lote")
def atualizar_lote(id_lote: int, dados: LoteTingimentoUpdate, db: Session = Depends(get_db)):
    return LoteService.atualizar(db, id_lote, dados)


@router.delete(
    "/{id_lote}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui um lote sem rolos (409 se houver rolos)",
)
def excluir_lote(id_lote: int, db: Session = Depends(get_db)):
    LoteService.excluir(db, id_lote)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
