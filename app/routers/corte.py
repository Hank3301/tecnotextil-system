from fastapi import APIRouter, Depends, status
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
    description="Cria a Ordem de Corte e altera o status do rolo para `EM_CORTE`."
)
def criar_ordem_corte(
    dados_ordem: OrdemCorteCreate,
    db: Session = Depends(get_db)
):
    return CorteService.criar_ordem_corte(db=db, dados_ordem=dados_ordem)


@router.post(
    "/ordens/{id_ordem}/executar",
    response_model=OrdemCorteResponse,
    summary="Registra a execução do corte e realiza baixa no estoque",
    description=(
        "Baixa a metragem cortada do rolo, confirma a reserva (se houver) "
        "e reclassifica automaticamente como retalho se a sobra for <= 5 metros (`RN-05`)."
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