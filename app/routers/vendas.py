from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_vendedor
from app.database import get_db
from app.schemas.schemas import (
    LoteTingimentoResponse,
    ReservaCreate,
    ReservaResponse
)
from app.services.reserva_service import ReservaService

router = APIRouter(
    prefix="/api/v1/vendas",
    tags=["Vendas & Reservas Temporárias"],
    dependencies=[Depends(require_vendedor)]
)


@router.get(
    "/estoque/lotes",
    response_model=List[LoteTingimentoResponse],
    summary="Consulta estoque agrupado por Lote de Tingimento (Partida)",
    description=(
        "Retorna a lista de lotes e rolos associados a um código de tecido. "
        "Garante a separação estrita por partida/cor e executa a limpeza prévia "
        "de reservas expiradas."
    )
)
def consultar_estoque_por_lote(
    cd_tecido: str = Query(..., description="Código comercial do tecido (ex: TEC-ALG-01)"),
    ds_tonalidade_cor: Optional[str] = Query(None, description="Filtro opcional por cor/tonalidade"),
    db: Session = Depends(get_db)
):
    lotes = ReservaService.consultar_estoque_por_lote(
        db=db,
        cd_tecido=cd_tecido,
        ds_tonalidade_cor=ds_tonalidade_cor
    )
    return lotes


@router.post(
    "/reservas",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma reserva temporária de metragem para um rolo",
    description=(
        "Bloqueia um rolo específico por 20 minutos (`RN-02`). "
        "Altera o status do rolo para `RESERVADO` se houver saldo suficiente."
    )
)
def criar_reserva(
    dados_reserva: ReservaCreate,
    db: Session = Depends(get_db)
):
    reserva = ReservaService.criar_reserva_temporaria(
        db=db,
        dados_reserva=dados_reserva
    )
    return reserva


@router.patch(
    "/reservas/{id_reserva}/cancelar",
    response_model=ReservaResponse,
    summary="Cancela manualmente uma reserva temporária ativa",
    description="Libera o rolo associado de volta para o status `DISPONIVEL` antes do prazo de expiração."
)
def cancelar_reserva(
    id_reserva: int,
    db: Session = Depends(get_db)
):
    reserva = ReservaService.cancelar_reserva(
        db=db,
        id_reserva=id_reserva
    )
    return reserva


@router.post(
    "/reservas/limpar-vencidas",
    summary="Dispara manualmente a rotina de limpeza de reservas vencidas",
    description="Endpoint utilitário/Job para expirar reservas cujo prazo de 20 min já encerrou."
)
def expirar_reservas_vencidas(
    db: Session = Depends(get_db)
):
    qtd_expiradas = ReservaService.expirar_reservas_vencidas(db=db)
    return {
        "status": "sucesso",
        "reservas_expiradas": qtd_expiradas,
        "mensagem": f"{qtd_expiradas} reserva(s) expirada(s) e rolo(s) liberado(s)."
    }