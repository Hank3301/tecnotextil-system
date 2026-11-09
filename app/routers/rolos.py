from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_gerente, require_operador
from app.database import get_db
from app.schemas.schemas import (
    MapeamentoDefeitoCreate, MapeamentoDefeitoResponse, RoloCreate, RoloResponse, RoloUpdate,
)
from app.services.rolo_service import RoloService

router = APIRouter(prefix="/api/v1/rolos", tags=["Cadastro de Rolos & Defeitos"])


# ----- Leitura: VENDEDOR, CORTADOR, GERENTE -----
@router.get("", response_model=List[RoloResponse], summary="Lista rolos com filtros", dependencies=[Depends(require_operador)])
def listar_rolos(
    id_lote: Optional[int] = Query(None),
    cd_tecido: Optional[str] = Query(None, description="Código comercial do tecido"),
    st_rolo: Optional[str] = Query(None, description="DISPONIVEL, RESERVADO, EM_CORTE, BLOQUEADO, INATIVO"),
    fl_retalho: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return RoloService.listar(
        db, id_lote=id_lote, cd_tecido=cd_tecido, st_rolo=st_rolo, fl_retalho=fl_retalho,
        skip=skip, limit=limit,
    )


@router.get(
    "/codigo-barras/{cd_barras}", response_model=RoloResponse,
    summary="Consulta um rolo pelo código de barras (leitura por scanner/PWA)",
    dependencies=[Depends(require_operador)],
)
def obter_rolo_por_codigo_barras(cd_barras: str, db: Session = Depends(get_db)):
    return RoloService.obter_por_codigo_barras(db, cd_barras)


@router.get("/{id_rolo}", response_model=RoloResponse, summary="Consulta um rolo", dependencies=[Depends(require_operador)])
def obter_rolo(id_rolo: int, db: Session = Depends(get_db)):
    return RoloService.obter(db, id_rolo)


@router.get(
    "/{id_rolo}/defeitos", response_model=List[MapeamentoDefeitoResponse],
    summary="Lista os defeitos mapeados do rolo",
    dependencies=[Depends(require_operador)],
)
def listar_defeitos(id_rolo: int, db: Session = Depends(get_db)):
    return RoloService.listar_defeitos(db, id_rolo)


# ----- Escrita: apenas GERENTE -----
@router.post(
    "", response_model=RoloResponse, status_code=status.HTTP_201_CREATED,
    summary="Cadastra um rolo (entra DISPONIVEL com saldo = metragem inicial)",
    dependencies=[Depends(require_gerente)],
)
def criar_rolo(dados: RoloCreate, db: Session = Depends(get_db)):
    return RoloService.criar(db, dados)


@router.patch(
    "/{id_rolo}", response_model=RoloResponse,
    summary="Atualiza localização e/ou status manual (DISPONIVEL, BLOQUEADO, INATIVO)",
    dependencies=[Depends(require_gerente)],
)
def atualizar_rolo(id_rolo: int, dados: RoloUpdate, db: Session = Depends(get_db)):
    return RoloService.atualizar(db, id_rolo, dados)


@router.delete(
    "/{id_rolo}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui um rolo sem histórico (409 se houver reservas/ordens)",
    dependencies=[Depends(require_gerente)],
)
def excluir_rolo(id_rolo: int, db: Session = Depends(get_db)):
    RoloService.excluir(db, id_rolo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------- Defeitos do rolo ----------------
@router.post(
    "/{id_rolo}/defeitos", response_model=MapeamentoDefeitoResponse, status_code=status.HTTP_201_CREATED,
    summary="Mapeia um defeito (intervalo em metros) no rolo",
    description="Os defeitos mapeados são usados na conferência de perdas na execução do corte.",
    dependencies=[Depends(require_gerente)],
)
def adicionar_defeito(id_rolo: int, dados: MapeamentoDefeitoCreate, db: Session = Depends(get_db)):
    return RoloService.adicionar_defeito(db, id_rolo, dados)


@router.delete(
    "/{id_rolo}/defeitos/{id_defeito}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove um defeito mapeado",
    dependencies=[Depends(require_gerente)],
)
def excluir_defeito(id_rolo: int, id_defeito: int, db: Session = Depends(get_db)):
    RoloService.excluir_defeito(db, id_rolo, id_defeito)
    return Response(status_code=status.HTTP_204_NO_CONTENT)