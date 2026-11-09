"""Router de relatórios gerenciais - Acesso restrito a GERENTE."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_gerente, UsuarioAutenticado
from app.database import get_db
from app.services.relatorio_service import RelatorioService

router = APIRouter(
    prefix="/api/v1/relatorios",
    tags=["Relatórios Gerenciais"],
    dependencies=[Depends(require_gerente)]
)


@router.get(
    "/retalhos",
    summary="Relatório de estoque de retalhos",
    description=(
        "Retorna métricas consolidadas do estoque de retalhos: "
        "quantidade total de rolos com fl_retalho=True, "
        "metragem acumulada e distribuição por tecido/lote. "
        "Restrito a usuários com cargo GERENTE."
    )
)
def relatorio_retalhos(
    current_user: UsuarioAutenticado = Depends(require_gerente),
    db: Session = Depends(get_db)
):
    return RelatorioService.relatorio_retalhos(db)


@router.get(
    "/perdas",
    summary="Relatório de perdas e divergências",
    description=(
        "Retorna consolidado de desperdícios das ordens de corte concluídas: "
        "soma total de metragem perdida, contagem de ordens com divergência "
        "e detalhamento por partida/lote. Restrito a usuários com cargo GERENTE."
    )
)
def relatorio_perdas(
    current_user: UsuarioAutenticado = Depends(require_gerente),
    db: Session = Depends(get_db)
):
    return RelatorioService.relatorio_perdas(db)


@router.get(
    "/rolo/{id_rolo}/historico",
    summary="Histórico completo de um rolo",
    description=(
        "Retorna a linha do tempo completa do rolo: dados cadastrais, "
        "defeitos mapeados, histórico de reservas e ordens de corte. "
        "Restrito a usuários com cargo GERENTE."
    )
)
def historico_rolo(
    id_rolo: int,
    current_user: UsuarioAutenticado = Depends(require_gerente),
    db: Session = Depends(get_db)
):
    historico = RelatorioService.historico_rolo(db, id_rolo)

    if not historico:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rolo com id {id_rolo} não encontrado"
        )

    return historico