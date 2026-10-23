from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import (
    OrdemCorteCreate,
    OrdemCorteExecucao,
    OrdemCorteResponse
)
from app.services.corte_service import CorteService

router = APIRouter(
    prefix="/api/v1/corte",
    tags=["Mesa de Corte & Gestão de Retalhos"]
)


@router.post(
    "/ordens",
    response_model=OrdemCorteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gera uma nova Ordem de Corte",
    description=(
        "Cria a Ordem de Corte e altera o status do rolo para `EM_CORTE`. "
        "Valida saldo do rolo e, se informada, a reserva (pertence ao rolo, ativa, não vencida). "
        "Rolo `RESERVADO` exige o `id_reserva`. A reserva vinculada passa a `CONFIRMADA`."
    )
)
def criar_ordem_corte(
    dados_ordem: OrdemCorteCreate,
    db: Session = Depends(get_db)
):
    return CorteService.criar_ordem_corte(db=db, dados_ordem=dados_ordem)


@router.get(
    "/ordens",
    response_model=List[OrdemCorteResponse],
    summary="Lista ordens de corte (mais recentes primeiro)"
)
def listar_ordens(
    st_ordem: Optional[str] = Query(None, description="PENDENTE, CONCLUIDA ou CANCELADA"),
    id_rolo: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    return CorteService.listar_ordens(db, st_ordem=st_ordem, id_rolo=id_rolo, skip=skip, limit=limit)


@router.get(
    "/ordens/{id_ordem}",
    response_model=OrdemCorteResponse,
    summary="Consulta uma ordem de corte"
)
def obter_ordem(id_ordem: int, db: Session = Depends(get_db)):
    return CorteService.obter_ordem(db, id_ordem)


@router.post(
    "/ordens/{id_ordem}/executar",
    response_model=OrdemCorteResponse,
    summary="Registra a execução do corte e realiza baixa no estoque",
    description=(
        "Só executa ordens `PENDENTE`. Baixa a metragem cortada, confere a perda "
        "(saldo esperado - sobra informada) contra os defeitos mapeados do rolo, adota a "
        "sobra informada como novo saldo e reclassifica como retalho se a sobra for <= 5 m (`RN-05`)."
    )
)
def executar_corte(
    id_ordem: int,
    dados_execucao: OrdemCorteExecucao,
    db: Session = Depends(get_db)
):
    return CorteService.executar_corte_e_baixar_estoque(
        db=db,
        id_ordem=id_ordem,
        dados_execucao=dados_execucao
    )


@router.patch(
    "/ordens/{id_ordem}/cancelar",
    response_model=OrdemCorteResponse,
    summary="Cancela uma ordem PENDENTE e devolve o rolo a DISPONIVEL"
)
def cancelar_ordem(id_ordem: int, db: Session = Depends(get_db)):
    return CorteService.cancelar_ordem(db, id_ordem)
